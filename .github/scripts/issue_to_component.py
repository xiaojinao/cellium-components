#!/usr/bin/env python3
"""把「提交组件」Issue 表单转成 components/<slug>/meta.json（以及可选的 README.md）。

只依赖 Python 标准库，和 scripts/build.py 保持同一套字段规则。

用法:
  python .github/scripts/issue_to_component.py                  # 从 ISSUE_BODY 读
  python .github/scripts/issue_to_component.py body.md --offline   # 本地调试
"""

import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import date

NL = chr(10)
TAB = chr(9)
CRLF = chr(13) + NL

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
COMPONENTS = os.path.join(ROOT, 'components')
OUT = os.path.join(ROOT, '.submission')
UA = 'cellium-registry/1.0'

CATEGORIES = ['web', 'ai', 'security', 'interaction', 'automation', 'data', 'media', 'other']
SLUG_RE = re.compile(r'^[a-z0-9][a-z0-9_-]{1,39}$')
SEMVER_RE = re.compile(r'^[0-9]+[.][0-9]+[.][0-9]+$')
DATE_RE = re.compile(r'^[0-9]{4}-[0-9]{2}-[0-9]{2}$')
HTTPS_RE = re.compile(r'^https://[^ ]+$')
LOGIN_RE = re.compile(r'^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$')
FENCE_RE = re.compile(r'\A```[^\n]*\n(.*)\n```\Z', re.S)


def noreply(login, uid=''):
    return (str(uid) + '+' + login if uid else login) + '@users.noreply.github.com'


def repo_owner(url):
    m = re.match(r'^https?://(?:www[.])?github[.]com/([^/#?]+)', str(url or ''), re.I)
    return m.group(1).lower() if m else ''


def read_text(path):
    try:
        with open(path, encoding='utf-8', errors='replace') as fh:
            return fh.read()
    except OSError:
        return ''


def pending_prs(slug, offline):
    repo = os.environ.get('GITHUB_REPOSITORY', '')
    token = os.environ.get('GITHUB_TOKEN', '')
    if offline or not repo or not token or not slug:
        return []
    url = 'https://api.github.com/repos/' + repo + '/pulls?state=open&per_page=100'
    req = urllib.request.Request(url, headers={
        'Authorization': 'Bearer ' + token,
        'Accept': 'application/vnd.github+json',
        'User-Agent': UA,
    })
    try:
        with urllib.request.urlopen(req, timeout=8) as res:
            data = json.loads(res.read().decode('utf-8', 'replace'))
    except (urllib.error.URLError, OSError, ValueError, TimeoutError):
        return []
    prefix = 'component/' + slug
    out = []
    for pr in data if isinstance(data, list) else []:
        ref = str((pr.get('head') or {}).get('ref') or '')
        if ref == prefix or ref.startswith(prefix + '-'):
            out.append(str(pr.get('number')))
    return out


LABELS = {
    'name': '组件名称',
    'slug': '组件标识（slug）',
    'summary': '一句话简介',
    'category': '分类',
    'tags': '标签（可选，逗号分隔）',
    'author': '作者名称',
    'repo': '源码仓库地址',
    'license': '许可证',
    'cover': '封面图地址（可选）',
    'version': '版本号',
    'vdate': '版本发布日期（可选）',
    'download': '安装包直链',
    'min_agent': '最低 Agent 版本（可选）',
    'changelog': '更新日志（可选）',
    'readme': '组件说明 / README（可选）',
    'confirm': '提交确认',
}


def split_section(body, label, stop_label=None):
    """切出一段表单内容，并从 body 中移除，避免最后一段把后面的内容一起吞进去。

    stop_label 用于 README 这类多行内容：它的正文里可以有自己的 '### 标题'，
    所以只能停在下一个已知的段（提交确认）前，不能停在任意 '### ' 前。
    """
    mark = '### ' + label
    idx = body.find(mark)
    if idx < 0:
        return '', body
    start = idx + len(mark)
    if stop_label:
        stop_idx = body.find('### ' + stop_label, start)
        end = stop_idx if stop_idx >= 0 else len(body)
    else:
        nxt = body.find(NL + '### ', start)
        end = nxt + 1 if nxt >= 0 else len(body)
    return body[start:end].strip(), body[:idx] + body[end:]


def parse_form(body):
    values = {}
    values['readme'], body = split_section(body, LABELS['readme'], LABELS['confirm'])
    values['confirm'], body = split_section(body, LABELS['confirm'])
    for key, label in LABELS.items():
        if key in ('readme', 'confirm'):
            continue
        values[key], body = split_section(body, label)
    return values


SINGLE_LINE_KEYS = {
    'name', 'slug', 'summary', 'category', 'tags', 'author', 'repo', 'license',
    'cover', 'version', 'vdate', 'download', 'min_agent', 'changelog',
}


def strip_outer_fence(text):
    """表单里把整段 README 包进 ```markdown 代码块是很常见的粘贴习惯，写盘前去掉这层围栏。

    不去掉的话，页面会把整篇 README 当成一个代码块渲染，看起来就像"Markdown 解析坏了"。
    """
    text = (text or '').strip()
    m = FENCE_RE.match(text)
    return m.group(1).strip() if m else text


def clean(value, single_line=False):
    text = (value or '').strip()
    if text in ('_No response_', '_没有提供答复_'):
        return ''
    text = text.replace(CRLF, NL).replace(chr(13), NL)
    if single_line:
        # 表单里换行粘贴很常见，单行字段统一压成一行，避免写进 meta.json 后变脏
        text = ' '.join(text.split())
    return text


def probe(url):
    try:
        req = urllib.request.Request(url, method='HEAD', headers={'User-Agent': UA})
        with urllib.request.urlopen(req, timeout=20) as res:
            return res.status
    except urllib.error.HTTPError as err:
        if err.code not in (403, 405, 501):
            return err.code
    except Exception:
        return 0
    try:
        req = urllib.request.Request(url, method='GET', headers={'User-Agent': UA, 'Range': 'bytes=0-0'})
        with urllib.request.urlopen(req, timeout=20) as res:
            return res.status
    except urllib.error.HTTPError as err:
        return err.code
    except Exception:
        return 0


def detect_indent(path):
    try:
        with open(path, encoding='utf-8') as fh:
            head = fh.read(600)
        for line in head.split(NL)[1:4]:
            if line.startswith(TAB):
                return TAB
    except OSError:
        pass
    return 2


def snapshot(paths):
    data = {}
    for path in paths:
        try:
            with open(path, encoding='utf-8') as fh:
                data[path] = fh.read()
        except OSError:
            data[path] = None
    return data


def rollback(data):
    for path, content in data.items():
        if content is None:
            if os.path.isfile(path):
                os.remove(path)
        else:
            with open(path, 'w', encoding='utf-8') as fh:
                fh.write(content)


def verify_with_build(slug):
    """用仓库自带的构建脚本兜底校验一次，只关心本 slug 的错误。"""
    script = os.path.join(ROOT, 'scripts', 'build.py')
    if not os.path.isfile(script):
        return []
    try:
        proc = subprocess.run(
            [sys.executable, script, '--check', '--skip-remote'],
            capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=300,
        )
    except Exception:
        return []
    if proc.returncode == 0:
        return []
    problems = []
    for line in ((proc.stderr or '') + (proc.stdout or '')).splitlines():
        line = line.strip()
        if not line.startswith('- '):
            continue
        item = line[2:].strip()
        if item.startswith(slug + ':'):
            problems.append('构建校验未通过：' + item[len(slug) + 1:].strip())
    return problems


def main():
    argv = [a for a in sys.argv[1:] if not a.startswith('--')]
    offline = '--offline' in sys.argv or os.environ.get('OFFLINE') == '1'

    body = os.environ.get('ISSUE_BODY', '')
    if not body and argv:
        with open(argv[0], encoding='utf-8') as fh:
            body = fh.read()

    issue_number = os.environ.get('ISSUE_NUMBER', '0')
    issue_author = os.environ.get('ISSUE_AUTHOR', '').lstrip('@')
    issue_author_id = os.environ.get('ISSUE_AUTHOR_ID', '')

    raw = parse_form(body)
    v = {key: clean(raw.get(key, ''), key in SINGLE_LINE_KEYS) for key in LABELS}
    v['readme'] = strip_outer_fence(v['readme'])

    errors = []
    warnings = []

    if not v['name']:
        errors.append('组件名称为必填项')
    elif len(v['name']) > 60:
        errors.append('组件名称不得超过 60 字')

    if not v['slug']:
        errors.append('组件标识（slug）为必填项')
    elif not SLUG_RE.match(v['slug']):
        errors.append('组件标识只能用小写字母、数字、中划线、下划线，2-40 位')

    if not v['summary']:
        errors.append('一句话简介为必填项')
    elif len(v['summary']) > 160:
        errors.append('一句话简介不得超过 160 字')

    if not v['category']:
        errors.append('分类为必填项')
    elif v['category'] not in CATEGORIES:
        errors.append('分类只能是：' + ' / '.join(CATEGORIES))

    if not v['version']:
        errors.append('版本号为必填项')
    elif not SEMVER_RE.match(v['version']):
        errors.append('版本号必须是三段式数字，例如 1.0.0')

    today = date.today().isoformat()
    vdate = v['vdate'] or today
    if not DATE_RE.match(vdate):
        errors.append('版本发布日期格式应为 2026-11-03')
    else:
        try:
            date.fromisoformat(vdate)
        except ValueError:
            errors.append('版本发布日期不是真实存在的日期：' + vdate)

    if not v['download']:
        errors.append('安装包直链为必填项')
    elif not HTTPS_RE.match(v['download']):
        errors.append('安装包直链必须是不带空格的 https 地址')

    for key, label, limit in (('author', '作者名称', 60), ('repo', '源码仓库地址', 300), ('license', '许可证', 40)):
        if len(v[key]) > limit:
            errors.append(label + '过长')

    if v['repo'] and not HTTPS_RE.match(v['repo']):
        errors.append('源码仓库地址必须是 https 地址')

    if v['cover'] and not HTTPS_RE.match(v['cover']):
        errors.append('封面图地址必须是不带空格的 https 地址')
    elif v['cover'] and len(v['cover']) > 800:
        errors.append('封面图地址超过 800 字符')

    if v['min_agent'] and not SEMVER_RE.match(v['min_agent']):
        errors.append('最低 Agent 版本必须是三段式数字，例如 0.9.0')

    if len(v['changelog']) > 500:
        errors.append('更新日志不得超过 500 字')

    if not v['confirm'] or '[x]' not in v['confirm'].lower():
        errors.append('需要勾选提交确认项')

    tags = [t.strip() for t in re.split(r'[,，]', v['tags']) if t.strip()] if v['tags'] else []
    if len(tags) > 8:
        errors.append('标签最多 8 个')
    if any(len(t) > 20 for t in tags):
        errors.append('单个标签不得超过 20 字')

    slug = v['slug'] or 'unknown'
    target_dir = os.path.join(COMPONENTS, slug)
    meta_path = os.path.join(target_dir, 'meta.json')

    existing = None
    if v['slug'] and os.path.isfile(meta_path):
        try:
            with open(meta_path, encoding='utf-8') as fh:
                existing = json.load(fh)
        except (OSError, ValueError):
            warnings.append('已存在的 meta.json 解析失败，本次忽略其历史版本')

    if existing:
        old_repo = str(existing.get('repo') or '').rstrip('/')
        new_repo = v['repo'].rstrip('/')
        if old_repo and new_repo and old_repo.lower() != new_repo.lower():
            errors.append('组件标识 ' + slug + ' 已被其他仓库占用，请更换标识')
        owner = str(existing.get('submitted_by') or '').lower() or repo_owner(old_repo or new_repo)
        if owner and issue_author and owner != issue_author.lower():
            errors.append(
                '该标识由 @' + owner + ' 提交，只有作者本人或仓库 owner 可以更新；'
                '如确需代办，请让作者本人提交本 Issue'
            )

    versions = list((existing or {}).get('versions') or [])
    same = None
    if v['version']:
        for item in versions:
            if str(item.get('version')) == v['version']:
                same = item
                break

    author_display = v['author'] or (existing or {}).get('author') or issue_author or slug
    existing_readme = read_text(os.path.join(target_dir, 'README.md'))

    def _meta_same(old):
        if not old:
            return False
        return (
            str(old.get('name') or '') == v['name']
            and str(old.get('summary') or '') == v['summary']
            and str(old.get('category') or '') == v['category']
            and list(old.get('tags') or []) == tags
            and str(old.get('author') or '') == author_display
            and str(old.get('repo') or '').rstrip('/') == v['repo'].rstrip('/')
            and str(old.get('license') or '') == v['license']
            and str(old.get('cover') or '') == v['cover']
            and (not v['readme'] or v['readme'].rstrip() == existing_readme.rstrip())
        )

    meta_change = existing is not None and not _meta_same(existing)

    noop = False
    if same is not None:
        if str(same.get('download') or '') != v['download']:
            errors.append('版本 ' + v['version'] + ' 已存在；同版本号不允许换包，请提升版本号')
        elif str(same.get('date') or '') != vdate:
            warnings.append('版本 ' + v['version'] + ' 的发布日期更新为 ' + vdate)
            versions = [dict(x, date=vdate) if str(x.get('version')) == v['version'] else x for x in versions]
        elif v['changelog'] and str(same.get('changelog') or '') != v['changelog']:
            warnings.append('版本 ' + v['version'] + ' 的更新日志已更新')
            versions = [dict(x, changelog=v['changelog']) if str(x.get('version')) == v['version'] else x for x in versions]
        elif not meta_change:
            warnings.append('版本与元信息均未变化，本次不产生改动')
            noop = True

    if not offline and not errors:
        status = probe(v['download'])
        if status == 404:
            errors.append('安装包直链返回 404，请确认是 Release 附件地址')
        elif status == 0:
            warnings.append('安装包直链无法连通，已跳过自动校验')
        elif status in (401, 403, 429):
            warnings.append('安装包直链暂时无法自动校验（HTTP ' + str(status) + '）')
        elif status >= 400:
            errors.append('安装包直链返回 HTTP ' + str(status))

        if v['repo']:
            rst = probe(v['repo'])
            if rst == 404:
                errors.append('源码仓库地址返回 404')
            elif rst >= 400 and rst not in (401, 403, 429):
                errors.append('源码仓库地址返回 HTTP ' + str(rst))
            elif rst in (0, 401, 403, 429):
                warnings.append('源码仓库地址暂时无法自动校验')

    if not errors and slug:
        busy = [n for n in pending_prs(slug, offline) if n != str(issue_number)]
        if busy:
            warnings.append(
                '该标识已有待合并的提交（#' + ' #'.join(busy[:3]) + '），'
                '对方先合并时本 PR 会冲突，届时需要重新提交一次'
            )

    ok = len(errors) == 0
    noop = bool(noop and ok)
    os.makedirs(OUT, exist_ok=True)

    trailers = []
    commit_author = ''
    if LOGIN_RE.match(issue_author):
        commit_author = issue_author + ' <' + noreply(issue_author, issue_author_id) + '>'
    claimed = (v['author'] or '').lstrip('@')
    if claimed and LOGIN_RE.match(claimed) and claimed.lower() != str(issue_author).lower():
        trailers.append('Co-authored-by: ' + claimed + ' <' + noreply(claimed) + '>')
    coauthor = NL.join(trailers)

    action_word = 'update' if existing else 'add'
    pr_title = 'feat(component): ' + action_word + ' ' + (v['name'] or slug) + ' (' + slug + ')'
    issue_tag = str(issue_number).strip()
    branch = 'component/' + slug + ('-' + issue_tag if issue_tag and issue_tag != '0' else '')

    readme_path = os.path.join(target_dir, 'README.md')
    before = snapshot([meta_path, readme_path]) if ok and not noop else {}

    if ok and not noop:
        if same is None:
            entry = {'version': v['version'], 'date': vdate, 'download': v['download']}
            if v['changelog']:
                entry['changelog'] = v['changelog']
            if v['min_agent']:
                entry['min_agent'] = v['min_agent']
            versions = [entry] + versions

        meta = {
            'slug': slug,
            'name': v['name'],
            'summary': v['summary'],
            'category': v['category'],
            'tags': tags,
            'author': author_display,
            'versions': versions,
        }
        repo = v['repo'] or (existing or {}).get('repo')
        license_ = v['license'] or (existing or {}).get('license')
        cover = v['cover'] or (existing or {}).get('cover')
        for key, val in (('repo', repo), ('license', license_), ('cover', cover)):
            if val:
                meta[key] = val
        for key in ('deprecated', 'source'):
            if existing and key in existing:
                meta[key] = existing[key]

        submitter = str((existing or {}).get('submitted_by') or issue_author or '')
        if submitter:
            meta['submitted_by'] = submitter

        os.makedirs(target_dir, exist_ok=True)
        indent = detect_indent(meta_path)
        with open(meta_path, 'w', encoding='utf-8') as fh:
            fh.write(json.dumps(meta, ensure_ascii=False, indent=indent))
            fh.write(NL)

        if v['readme']:
            with open(readme_path, 'w', encoding='utf-8') as fh:
                fh.write(v['readme'].rstrip() + NL)

        problems = verify_with_build(slug)
        if problems:
            errors.extend(problems)
            ok = False
            rollback(before)

    lines = []
    if ok:
        lines.append('## 自动校验通过')
        lines.append('')
        lines.append('- 名称：' + v['name'])
        lines.append('- 标识：`' + slug + '`')
        lines.append('- 分类：' + v['category'])
        lines.append('- 版本：' + v['version'] + '（' + vdate + '）')
        lines.append('- 直链：' + v['download'])
        if tags:
            lines.append('- 标签：' + '、'.join(tags))
        lines.append('')
        if existing:
            lines.append('该标识已收录，本次按新版本更新到 ' + v['version'] + '。')
            lines.append('')
        if warnings:
            lines.append('> 提示')
            for warn in warnings:
                lines.append('> - ' + warn)
            lines.append('')
        if noop:
            lines.append('没有需要写入的改动，本次不创建 Pull Request。')
        else:
            lines.append('已生成 `components/' + slug + '/meta.json`，正在创建 Pull Request，合并后自动上线。')
    else:
        lines.append('## 自动校验未通过')
        lines.append('')
        for err in errors:
            lines.append('- ' + err)
        lines.append('')
        if warnings:
            lines.append('> 提示')
            for warn in warnings:
                lines.append('> - ' + warn)
            lines.append('')
        lines.append('请直接编辑本 Issue 修正后保存，机器人会自动重新校验。')

    with open(os.path.join(OUT, 'comment.md'), 'w', encoding='utf-8') as fh:
        fh.write(NL.join(lines) + NL)

    pr_body = NL.join([
        '自动生成自 #' + issue_number,
        '',
        '| 字段 | 值 |',
        '| --- | --- |',
        '| 标识 | `' + slug + '` |',
        '| 分类 | ' + (v['category'] or '-') + ' |',
        '| 版本 | ' + (v['version'] or '-') + ' |',
        '| 直链 | ' + (v['download'] or '-') + ' |',
        '| 作者 | ' + author_display + ' |',
        '',
        'Closes #' + issue_number,
    ]) + NL
    with open(os.path.join(OUT, 'pr-body.md'), 'w', encoding='utf-8') as fh:
        fh.write(pr_body)

    result = {
        'ok': ok,
        'noop': noop,
        'commit_author': commit_author,
        'slug': slug,
        'errors': errors,
        'warnings': warnings,
        'branch': branch,
        'pr_title': pr_title,
        'coauthor': coauthor,
    }
    with open(os.path.join(OUT, 'result.json'), 'w', encoding='utf-8') as fh:
        fh.write(json.dumps(result, ensure_ascii=False, indent=2) + NL)

    go = os.environ.get('GITHUB_OUTPUT')
    if go:
        single = {
            'ok': str(ok).lower(),
            'noop': str(noop).lower(),
            'slug': slug,
            'branch': branch,
            'pr_title': pr_title,
            'commit_author': commit_author,
        }
        with open(go, 'a', encoding='utf-8') as fh:
            for key, val in single.items():
                fh.write(key + '=' + str(val).replace(NL, ' ').replace('\r', ' ') + NL)
            fh.write('coauthor<<__CELLIUM_COAUTHOR__' + NL + coauthor + NL + '__CELLIUM_COAUTHOR__' + NL)

    print(json.dumps({'ok': ok, 'slug': slug, 'errors': errors, 'warnings': warnings}, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
