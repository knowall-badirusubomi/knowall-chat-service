#!
echo "[Unit]
Description=Gunicorn instance to serve Flask
After=network.target

[Service]
User=test
WorkingDirectory=/home/test/flaskapp/
ExecStart=/home/test/myvirtual/bin/gunicorn --worker-class eventlet -w 1 myapp:app --bind 0.0.0.0:5000
Restart=always


[Install]
WantedBy=multi-user.target" >> etc/systemd/system/myapp.service