# LVM Snapshot Backup
*Create COW snapshot of LVM volume and do backup from that without interrupting work. Use **--listed-incremental** option with **tar** to store imake archives*

## Use:

    snap-backup.sh <options>

### Command-Line Arguments

 - -z - *<0|1> full backup 1 - yearly, 0 - monthly*
 - -v - *logical volume name to backup*
 - -g - *volume vroup name where logical volume located*
 - -m - *path to mount snaphot volume*
 - -b - *path to store backup archives*
 - -s - *size of snapshot*