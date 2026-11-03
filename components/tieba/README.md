# 百度贴吧（tieba）                                                                     
                                                                                         
 给 Cellium Agent                                                                        
 加上「逛贴吧」的能力：看吧、看帖、看楼层、搜吧搜帖、查用户，登录后还能读自己的关注/帖子 
 /回复/@。                                                                               
                                                                                         
 ## 安装                                                                                 
                                                                                         
 1. 市场安装，或把 `tieba.py` 放进 `components/` 目录                                    
 2. 安装依赖：`pip install aiotieba`                                                     
                                                                                         
 无需登录即可使用浏览类命令；登录后才可读取个人数据。                                    
                                                                                         
 ## 命令                                                                                 
                                                                                         
 | 命令 | 作用 | 需要登录 |                                                              
 |---|---|---|                                                                           
 | forum | 吧信息 | |                                                                    
 | threads | 吧内主题列表（sort: reply/new/hot/follow） | |                              
 | posts | 帖子正文与楼层 | |                                                            
 | user | 用户主页信息 | |                                                               
 | search | 搜吧 | |                                                                     
 | search_in | 吧内搜帖 | |                                                              
 | cookie | 保存/查看 BDUSS + STOKEN | |                                                 
 | whoami | 当前登录账号 | ✔ |                                                           
 | my_forums | 我关注的吧 | ✔ |                                                          
 | my_threads | 我发布的主题 | ✔ |                                                       
 | replies | 回复我的 | ✔ |                                                              
 | ats | @我的 | ✔ |                                                                     
 | bg_start / bg_stop | 启停后台闲逛 | |                                                 
 | bg_status | 后台状态（下次触发、今日次数） | |                                        
 | bg_run | 立即触发一次 | |                                                             
 | bg_subscribe / bg_unsubscribe | 订阅/取消推送会话 | |                                 
                                                                                         
 ## 配置                                                                                 
                                                                                         
 - 推送目标：环境变量 `TIEBA_TARGET_SESSION`（例如                                       
 `qq:xxxx`、`napcat:group:123456`）。留空则不主动推送。                                  
 - 也可在任意会话里执行 bg_subscribe，把当前会话加成推送目标。                           
 - 后台闲逛默认冷却 90–180 分钟、每天最多 6 次、凌晨 1 点到早 8                          
 点静默，可在源码顶部常量调整。                                                          
                                                                                         
 ## 隐私                                                                                 
                                                                                         
 - 登录 Cookie 只写入本机 `~/.cellium/secrets/tieba_cookie.json`，目录权限               
 0700，不会上传到任何地方。                                                              
 - 组件本身不含任何账号、群号、会话 ID 或路径等个人数据。                                
 - 网络请求只发往贴吧官方域名（经 aiotieba）。                                           
                                                                                         
 ## 说明                                                                                 
                                                                                         
 后台闲逛只是「抓一批候选帖 → 交给 Agent                                                 
 生成口语化一句话」，不会自动发帖、不会回复、不会点赞。
