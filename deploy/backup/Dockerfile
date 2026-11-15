# Off-site copy of the nightly database backups: rclone sends them, encrypted,
# to a Google Drive folder of their own ("App Sport"). The encryption keys are
# yours and live only in Coolify's variables (and your secrets folder on the PC).
FROM rclone/rclone:1.71.2
COPY backup-loop.sh /usr/local/bin/backup-loop.sh
ENTRYPOINT ["/bin/sh", "/usr/local/bin/backup-loop.sh"]
