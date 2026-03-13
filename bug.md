检查容器状态...
WARN[0000] /root/case_analysis_web/docker-compose.yml: `version` is obsolete 
NAME                  IMAGE                                 COMMAND                  SERVICE               CREATED          STATUS                        PORTS
case-analysis-web     case_analysis_web-case-analysis-app   "gunicorn --bind 0.0…"   case-analysis-app     21 seconds ago   Restarting (1) 1 second ago   
mysql-case-analysis   mysql:8.0                             "docker-entrypoint.s…"   mysql-case-analysis   21 seconds ago   Up 20 seconds (healthy)       0.0.0.0:3306->3306/tcp, :::3306->3306/tcp, 33060/tcp

查看服务日志...
WARN[0000] /root/case_analysis_web/docker-compose.yml: `version` is obsolete 
mysql-case-analysis  | 2026-03-13 16:45:40+00:00 [Note] [Entrypoint]: Entrypoint script for MySQL Server 8.0.45-1.el9 started.
mysql-case-analysis  | 2026-03-13 16:45:40+00:00 [Note] [Entrypoint]: Switching to dedicated user 'mysql'
mysql-case-analysis  | 2026-03-13 16:45:41+00:00 [Note] [Entrypoint]: Entrypoint script for MySQL Server 8.0.45-1.el9 started.
mysql-case-analysis  | '/var/lib/mysql/mysql.sock' -> '/var/run/mysqld/mysqld.sock'
mysql-case-analysis  | 2026-03-13T16:45:41.340386Z 0 [Warning] [MY-011068] [Server] The syntax '--skip-host-cache' is deprecated and will be removed in a future release. Please use SET GLOBAL host_cache_size=0 instead.
mysql-case-analysis  | 2026-03-13T16:45:41.341194Z 0 [Warning] [MY-010918] [Server] 'default_authentication_plugin' is deprecated and will be removed in a future release. Please use authentication_policy instead.
mysql-case-analysis  | 2026-03-13T16:45:41.341210Z 0 [System] [MY-010116] [Server] /usr/sbin/mysqld (mysqld 8.0.45) starting as process 1
mysql-case-analysis  | 2026-03-13T16:45:41.346483Z 1 [System] [MY-013576] [InnoDB] InnoDB initialization has started.
mysql-case-analysis  | 2026-03-13T16:45:41.703910Z 1 [System] [MY-013577] [InnoDB] InnoDB initialization has ended.
mysql-case-analysis  | 2026-03-13T16:45:41.886002Z 0 [Warning] [MY-010068] [Server] CA certificate ca.pem is self signed.
mysql-case-analysis  | 2026-03-13T16:45:41.886045Z 0 [System] [MY-013602] [Server] Channel mysql_main configured to support TLS. Encrypted connections are now supported for this channel.
mysql-case-analysis  | 2026-03-13T16:45:41.888951Z 0 [Warning] [MY-011810] [Server] Insecure configuration for --pid-file: Location '/var/run/mysqld' in the path is accessible to all OS users. Consider choosing a different directory.
mysql-case-analysis  | 2026-03-13T16:45:41.919460Z 0 [System] [MY-011323] [Server] X Plugin ready for connections. Bind-address: '::' port: 33060, socket: /var/run/mysqld/mysqlx.sock
mysql-case-analysis  | 2026-03-13T16:45:41.919509Z 0 [System] [MY-010931] [Server] /usr/sbin/mysqld: ready for connections. Version: '8.0.45'  socket: '/var/run/mysqld/mysqld.sock'  port: 3306  MySQL Community Server - GPL.
mysql-case-analysis  | 2026-03-13T16:45:50.866836Z 8 [Warning] [MY-013360] [Server] Plugin mysql_native_password reported: ''mysql_native_password' is deprecated and will be removed in a future release. Please use caching_sha2_password instead'
case-analysis-web    |     raise RuntimeError("gevent worker requires gevent 1.4 or higher")
case-analysis-web    | RuntimeError: gevent worker requires gevent 1.4 or higher
case-analysis-web    | ]
case-analysis-web    | 
case-analysis-web    | 
case-analysis-web    | Error: class uri 'gevent' invalid or not found: 
case-analysis-web    | 
case-analysis-web    | [Traceback (most recent call last):
case-analysis-web    |   File "/usr/local/lib/python3.9/site-packages/gunicorn/workers/ggevent.py", line 13, in <module>
case-analysis-web    |     import gevent
case-analysis-web    | ModuleNotFoundError: No module named 'gevent'
case-analysis-web    | 
case-analysis-web    | During handling of the above exception, another exception occurred:
case-analysis-web    | 
case-analysis-web    | Traceback (most recent call last):
case-analysis-web    |   File "/usr/local/lib/python3.9/site-packages/gunicorn/util.py", line 111, in load_class
case-analysis-web    |     mod = importlib.import_module('.'.join(components))
case-analysis-web    |   File "/usr/local/lib/python3.9/importlib/__init__.py", line 127, in import_module
case-analysis-web    |     return _bootstrap._gcd_import(name[level:], package, level)
case-analysis-web    |   File "<frozen importlib._bootstrap>", line 1030, in _gcd_import
case-analysis-web    |   File "<frozen importlib._bootstrap>", line 1007, in _find_and_load
case-analysis-web    |   File "<frozen importlib._bootstrap>", line 986, in _find_and_load_unlocked
case-analysis-web    |   File "<frozen importlib._bootstrap>", line 680, in _load_unlocked
case-analysis-web    |   File "<frozen importlib._bootstrap_external>", line 850, in exec_module
case-analysis-web    |   File "<frozen importlib._bootstrap>", line 228, in _call_with_frames_removed
case-analysis-web    |   File "/usr/local/lib/python3.9/site-packages/gunicorn/workers/ggevent.py", line 15, in <module>
case-analysis-web    |     raise RuntimeError("gevent worker requires gevent 1.4 or higher")
case-analysis-web    | RuntimeError: gevent worker requires gevent 1.4 or higher
case-analysis-web    | ]
case-analysis-web    | 