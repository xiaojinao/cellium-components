#!/usr/bin/env python3
"""构建组件索引：索引仓库只有 meta.json，源码在作者自己的仓库（Release 直链或 meta.source）。

只用 Python 标准库，组件作者装了 Cellium Agent 就已经有 Python，不需要额外装 Node。

用法:
  python scripts/build.py              # 生成 dist/data + dist/pkg
  python scripts/build.py --check      # 只校验，不写文件（CI 用这个）
  python scripts/build.py --check --skip-remote   # 断网校验，不访问直链
  python scripts/build.py --out <dir>  # 输出到指定目录（服务器直写前端 dist）
  python scripts/build.py --tolerant   # 宽容模式：坏组件跳过并告警，不中断发布
"""

import argparse
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime, timezone

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
COMPONENTS = os.path.join(ROOT, 'components')
CACHE = os.path.join(ROOT, '.cache')

SEMVER = re.compile(r'^\d+\.\d+\.\d+$')
DATE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')
SLUG_RE = re.compile(r'^[a-z0-9][a-z0-9_-]{1,39}$')
HTTPS_RE = re.compile(r'^https://[^\s]+$', re.IGNORECASE)

GIT_TIMEOUT = 180
HTTP_TIMEOUT = 20
UA = 'cellium-registry/1.0'


class BuildError(Exception):
    pass


class Reporter:
    def __init__(self):
        self.errors = []
        self.bad_slugs = set()

    def fail(self, slug, msg):
        self.errors.append(f'{slug}: {msg}')
        self.bad_slugs.add(slug)

    def warn(self, msg):
        print(f'  ! {msg}', file=sys.stderr)


rep = Reporter()


def exec_git(args, cwd=None):
    """跑 git，失败抛 BuildError（带 stderr 摘要）。"""
    try:
        return subprocess.run(
            ['git'] + args,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=GIT_TIMEOUT,
            check=True,
        )
    except FileNotFoundError:
        raise BuildError('找不到 git 命令')
    except subprocess.TimeoutExpired:
        raise BuildError('git 执行超时')
    except subprocess.CalledProcessError as e:
        detail = (e.stderr or b'').decode('utf-8', 'replace').strip().splitlines()
        raise BuildError(detail[-1] if detail else f'git 退出码 {e.returncode}')


def strip_slashes(value):
    return str(value or '').strip().rstrip('/')


def normalize_url(url):
    u = strip_slashes(url)
    if HTTPS_RE.match(u):
        return u
    if os.environ.get('CELLIUM_ALLOW_LOCAL_GIT') == '1' and u.startswith('file://'):
        return u
    raise BuildError(f'source.url 必须是 https:// 的 Git 地址（当前: {url}）')


def normalize_download(url):
    u = str(url or '').strip()
    if not HTTPS_RE.match(u):
        raise BuildError(f'download 必须是 https:// 直链（当前: {url}）')
    return u


def mirror_path(url):
    return os.path.join(CACHE, 'git', hashlib.sha1(url.encode('utf-8')).hexdigest()[:16])


def sync_mirror(url):
    """缓存镜像到 .cache/git/，之后只增量拉取。"""
    path = mirror_path(url)
    if os.path.exists(os.path.join(path, 'HEAD')):
        try:
            exec_git(['-C', path, 'fetch', '--tags', '--prune', '--quiet', 'origin'])
        except BuildError:
            rep.warn(f'拉取失败，使用本地缓存：{url}')
        return path
    os.makedirs(os.path.dirname(path), exist_ok=True)
    exec_git(['clone', '--mirror', '--quiet', url, path])
    return path


def resolve_commit(mirror, version):
    specs = [s for s in (version.get('commit'), version.get('ref'), version.get('tag')) if s]
    if not specs:
        raise BuildError('git 版本必须提供 commit 或 ref')
    for spec in specs:
        try:
            out = exec_git(['-C', mirror, 'rev-parse', '--verify', f'{spec}^{{commit}}'])
            return out.stdout.decode('utf-8', 'replace').strip()
        except BuildError:
            continue
    raise BuildError(f'找不到 commit/ref: {" / ".join(specs)}')


def export_tree(mirror, commit, subdir, work_dir):
    """git archive 导出到 tar，再解到 work_dir；返回源码目录。"""
    clean = str(subdir or '').strip('/').strip()
    if '..' in clean.split('/'):
        raise BuildError(f'source.subdir 非法: {subdir}')
    try:
        out = exec_git(['-C', mirror, 'archive', '--format=tar', '--prefix=repo/', commit])
    except BuildError as e:
        raise BuildError(f'导出 {commit[:8]} 失败: {e}')
    with tarfile.open(fileobj=io.BytesIO(out.stdout)) as tf:
        try:
            tf.extractall(work_dir, filter='data')
        except TypeError:  # Python < 3.11.4 没有 filter 参数
            tf.extractall(work_dir)
    target = os.path.join(work_dir, 'repo', clean) if clean else os.path.join(work_dir, 'repo')
    if not os.path.isdir(target):
        raise BuildError(f'source.subdir 不存在: {clean or "."}')
    return target


def zip_dir(src_dir, out_file):
    os.makedirs(os.path.dirname(out_file), exist_ok=True)
    with zipfile.ZipFile(out_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(src_dir):
            dirs[:] = [d for d in dirs if d != '__pycache__' and not (root == src_dir and d == '.git')]
            for name in sorted(files):
                if name.endswith('.pyc') or name == '.DS_Store':
                    continue
                full = os.path.join(root, name)
                rel = os.path.relpath(full, src_dir)
                zf.write(full, rel)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_opener = urllib.request.build_opener(_NoRedirect)


def check_download(url, skip_remote):
    """只探活（HEAD），不下载；返回 content-length，拿不到返回 None。"""
    if skip_remote:
        return None
    current = url
    for _ in range(10):
        req = urllib.request.Request(current, method='HEAD', headers={'User-Agent': UA})
        try:
            with _opener.open(req, timeout=HTTP_TIMEOUT) as res:
                length = int(res.headers.get('content-length') or 0)
                return length if length > 0 else None
        except urllib.error.HTTPError as e:
            if e.code in (301, 302, 303, 307, 308):
                location = e.headers.get('Location')
                if not location:
                    raise BuildError(f'下载地址返回 {e.code}（{url}）')
                current = urllib.parse.urljoin(current, location)
                continue
            raise BuildError(f'下载地址返回 {e.code}（{url}）')
        except urllib.error.URLError as e:
            raise BuildError(f'下载地址不可达: {e.reason}')
        except TimeoutError:
            raise BuildError('下载地址不可达: timeout')
    raise BuildError(f'下载地址重定向次数过多（{url}）')


def version_key(v):
    try:
        return tuple(int(x) for x in str(v).split('.'))
    except ValueError:
        return (0, 0, 0)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def build(out_dir, check_only, skip_remote, tolerant):
    slugs = set()
    items = []
    cat_count = {}

    for name in sorted(os.listdir(COMPONENTS)):
        base = os.path.join(COMPONENTS, name)
        if not os.path.isdir(base):
            continue
        meta_path = os.path.join(base, 'meta.json')
        if not os.path.isfile(meta_path):
            rep.fail(name, '缺少 meta.json')
            continue
        # 索引仓库只收元信息，组件源码必须留在作者自己的仓库
        if os.path.exists(os.path.join(base, 'src')):
            rep.fail(name, '索引仓库不接受组件源码，请删除 components/<slug>/src')
            continue

        try:
            with open(meta_path, encoding='utf-8') as f:
                meta = json.load(f)
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            rep.fail(name, f'meta.json 解析失败: {e}')
            continue

        for key in ('slug', 'name', 'summary', 'category', 'author'):
            if not isinstance(meta.get(key), str) or not meta.get(key):
                rep.fail(name, f'缺少或非法字段 {key}')
        if meta.get('slug') != name:
            rep.fail(name, f'slug ({meta.get("slug")}) 必须与目录名 ({name}) 一致')
        if not SLUG_RE.match(str(meta.get('slug') or '')):
            rep.fail(name, 'slug 只能是小写字母/数字/中划线/下划线，2-40 位')
        if meta.get('slug') in slugs:
            rep.fail(name, f'slug 重复: {meta.get("slug")}')
        slugs.add(meta.get('slug'))
        if isinstance(meta.get('name'), str) and len(meta['name']) > 60:
            rep.fail(name, 'name 超过 60 字')
        if isinstance(meta.get('summary'), str) and len(meta['summary']) > 160:
            rep.fail(name, 'summary 超过 160 字')

        if not isinstance(meta.get('tags'), list):
            meta['tags'] = []
        if len(meta['tags']) > 8:
            rep.fail(name, 'tags 最多 8 个')

        cover = meta.get('cover')
        if cover is not None and cover != '':
            if not isinstance(cover, str) or not HTTPS_RE.match(cover):
                rep.fail(name, 'cover 必须是不带空格的 https:// 图片地址')
            elif len(cover) > 800:
                rep.fail(name, 'cover 地址超过 800 字符')

        versions_in = meta.get('versions')
        if not isinstance(versions_in, list) or not versions_in:
            rep.fail(name, 'versions 至少一个')
            continue

        needs_source = any(not v.get('download') for v in versions_in)
        is_git = needs_source and isinstance(meta.get('source'), dict) and meta['source'].get('type') == 'git'
        mirror = None
        if needs_source and meta.get('source'):
            if meta['source'].get('type') != 'git':
                rep.fail(name, 'source.type 目前只支持 "git"')
            elif not meta['source'].get('url'):
                rep.fail(name, 'source.url 必填')
            else:
                try:
                    meta['source']['url'] = normalize_url(meta['source']['url'])
                    mirror = sync_mirror(meta['source']['url'])
                except BuildError as e:
                    rep.fail(name, str(e))

        seen = set()
        versions = []
        readme = ''

        for v in versions_in:
            version = v.get('version')
            if not isinstance(version, str) or not SEMVER.match(version):
                rep.fail(name, f'版本号非法: {version}')
            if version in seen:
                rep.fail(name, f'版本重复: {version}')
            seen.add(version)
            if not isinstance(v.get('date'), str) or not DATE_RE.match(v['date']):
                rep.fail(name, f'版本 {version} 日期格式应为 YYYY-MM-DD')

            # 直链模式：不 clone、不打包，只 HEAD 探活
            if v.get('download'):
                try:
                    url = normalize_download(v['download'])
                    size = check_download(url, skip_remote)
                    nv = dict(v)
                    nv['download'] = url
                    if size is not None:
                        nv['size'] = size
                    versions.append(nv)
                except BuildError as e:
                    rep.fail(name, f'版本 {version} {e}')
                continue

            if is_git:
                try:
                    if not mirror:
                        raise BuildError('源仓库不可用')
                    commit = resolve_commit(mirror, v)
                    work_dir = tempfile.mkdtemp(prefix='cellium-src-')
                    src_dir = export_tree(mirror, commit, meta['source'].get('subdir'), work_dir)
                    if not readme:
                        readme_path = os.path.join(src_dir, 'README.md')
                        if os.path.isfile(readme_path):
                            with open(readme_path, encoding='utf-8', errors='replace') as f:
                                readme = f.read()
                    nv = dict(v)
                    nv['commit'] = commit
                    nv['file'] = f'{meta.get("slug") or ""}-{version}.zip'
                    nv['_srcDir'] = src_dir
                    versions.append(nv)
                except BuildError as e:
                    rep.fail(name, f'拉取 {version} 失败: {e}')
                continue

            rep.fail(name, f'版本 {version} 缺少 download 直链或 source')

        # 直链模式没有源码目录可读，允许 components/<slug>/README.md 作为详情页正文
        if not readme:
            local_readme = os.path.join(base, 'README.md')
            if os.path.isfile(local_readme):
                with open(local_readme, encoding='utf-8', errors='replace') as f:
                    readme = f.read()

        versions.sort(key=lambda x: version_key(x['version']), reverse=True)

        if tolerant and name in rep.bad_slugs:
            rep.warn(f'跳过 {name}（校验未通过）')
            continue

        latest = versions[0] if versions else {}
        items.append({
            'slug': meta.get('slug') or '',
            'name': meta.get('name') or '',
            'summary': meta.get('summary') or '',
            'category': meta.get('category') or '',
            'tags': meta['tags'],
            'author': meta.get('author') or '',
            'repo': meta.get('repo') or (meta.get('source') or {}).get('url') or '',
            'license': meta.get('license') or '',
            'deprecated': bool(meta.get('deprecated')),
            'cover': meta.get('cover') or '',
            'source': meta.get('source') or None,
            'latest_version': latest.get('version', ''),
            'updated_at': latest.get('date', ''),
            'versions': [{k: val for k, val in v.items() if k != '_srcDir'} for v in versions],
            'readme': readme,
            '_versions': versions,
        })
        cat_count[meta.get('category') or ''] = cat_count.get(meta.get('category') or '', 0) + 1

    if rep.errors:
        lines = '\n'.join('  - ' + e for e in rep.errors)
        if not tolerant:
            print(f'\n✗ 校验失败（{len(rep.errors)} 项）:\n{lines}\n', file=sys.stderr)
            return 1
        print(f'\n! 已跳过 {len(rep.bad_slugs)} 个组件（{len(rep.errors)} 项问题）:\n{lines}\n', file=sys.stderr)

    total_versions = sum(len(i['versions']) for i in items)
    print(f'✓ 校验通过：{len(items)} 个组件，{total_versions} 个版本')
    if check_only:
        return 0

    # ---------- 输出 ----------
    shutil.rmtree(os.path.join(out_dir, 'data'), ignore_errors=True)
    shutil.rmtree(os.path.join(out_dir, 'pkg'), ignore_errors=True)
    os.makedirs(os.path.join(out_dir, 'data', 'c'), exist_ok=True)
    os.makedirs(os.path.join(out_dir, 'pkg'), exist_ok=True)

    # 先打包（回填 sha256/size），再写索引，保证索引里的校验值可用
    for item in items:
        for v in item['_versions']:
            if v.get('download'):
                continue  # 直链版本不打本地包
            out_zip = os.path.join(out_dir, 'pkg', f'{item["slug"]}-{v["version"]}.zip')
            try:
                zip_dir(v['_srcDir'], out_zip)
                v['sha256'] = sha256_file(out_zip)
                v['size'] = os.path.getsize(out_zip)
            except (OSError, zipfile.BadZipFile) as e:
                rep.warn(f'打包失败 {item["slug"]}@{v["version"]}: {e}')
        item['versions'] = [{k: val for k, val in v.items() if k != '_srcDir'} for v in item['_versions']]

    index = {
        'generated_at': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S'),
        'count': len(items),
        'categories': [
            {'key': k, 'count': c}
            for k, c in sorted(cat_count.items(), key=lambda kv: kv[1], reverse=True)
        ],
        'items': sorted(
            [{k: val for k, val in i.items() if k not in ('readme', '_versions')} for i in items],
            key=lambda i: i['updated_at'],
            reverse=True,
        ),
    }
    with open(os.path.join(out_dir, 'data', 'index.json'), 'w', encoding='utf-8') as f:
        f.write(json.dumps(index, ensure_ascii=False, indent=2))

    for item in items:
        detail = {k: item[k] for k in (
            'slug', 'name', 'summary', 'category', 'tags', 'author', 'repo', 'license',
            'deprecated', 'cover', 'source', 'latest_version', 'updated_at', 'readme', 'versions',
        )}
        with open(os.path.join(out_dir, 'data', 'c', f'{item["slug"]}.json'), 'w', encoding='utf-8') as f:
            f.write(json.dumps(detail, ensure_ascii=False, indent=2))

    print(f'✓ 输出到 {out_dir}')
    print('  data/index.json  data/c/*.json  pkg/*.zip')
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description='构建组件市场索引')
    parser.add_argument('--out', default=os.path.join(ROOT, 'dist'), help='输出目录，默认 dist')
    parser.add_argument('--check', action='store_true', help='只校验，不写文件')
    parser.add_argument('--skip-remote', action='store_true', help='不访问网络（直链只检查格式）')
    parser.add_argument('--tolerant', action='store_true', help='坏组件跳过并告警，不中断发布')
    args = parser.parse_args(argv)

    skip_remote = args.skip_remote or os.environ.get('CELLIUM_SKIP_REMOTE') == '1'
    out_dir = os.path.abspath(args.out)

    try:
        return build(out_dir, args.check, skip_remote, args.tolerant)
    except BuildError as e:
        print(f'\n✗ 构建失败: {e}\n', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
