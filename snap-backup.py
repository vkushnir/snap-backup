#!/usr/bin/python
"""
 This python module is used for backup data from LVM Volumes.
 Written by : Vladimir Kushnir
 Created date: 24.04.2019
 Last modified: 24.04.2019
 Tested with : Python 2.6.6
    Simple usage example:
"""

__version__ = "0.1"
__copyright__ = "Vladimir Kushnir aka Kvantum i(c)2019"

import argparse
# Import required python libraries
import os
import MySQLdb
import humanize
from subprocess import check_call, check_output

from datetime import datetime
import sys

# COMMANDS
LVCREATE_CMD = "/sbin/lvcreate"
LVREMOVE_CMD = "/sbin/lvremove"
MOUNT_CMD = "/bin/mount"
UMOUNT_CMD = "/bin/umount"
TAR_CMD = "/usr/bin/tar"
FIND_CMD = "/usr/bin/find"


def next_file(path, fn, ext):
    """find unique filename"""
    file_name = "{0:s}.{1:s}".format(fn, ext)
    if not os.path.isfile(os.path.join(path, file_name)):
        return file_name
    for n in range(1, 99):
        file_name = "{0:s}_{2:02d}.{1:s}".format(fn, ext, n)
        if not os.path.isfile(os.path.join(path, file_name)):
            return file_name
    else:
        print "can't find filename for archive!!!"
        sys.exit(1)


def get_options():
    """get commandline parameters"""
    parser = argparse.ArgumentParser(usage='%(prog)s [options]',
                                     description='Backup data from LVM Volume.\n'
                                                 'Creates COW snapshot from LVM volume,  archive it to TAR and exit')
    parser.add_argument('--version', action='version', version='%(prog)s ' + __version__)
    parser.set_defaults(bmode=('{:%Y-%m}', '{:%Y%m}'), zmode=('--verbose', 'tar'))

    group_backup = parser.add_argument_group('backup arguments')
    group_backup.add_argument('-f', '--force', action='store_true', default=False, dest='force',
                              help="create all folders if not exists")
    group_backup_mode = group_backup.add_mutually_exclusive_group()
    group_backup_mode.add_argument('--year', action='store_const', const=('{:%Y}', '{:%Y}'), dest='bmode',
                                   help="group archies every year in single folder")
    group_backup_mode.add_argument('--month', action='store_const', const=('{:%Y-%m}', '{:%Y%m}'), dest='bmode',
                                   help="group archies every month in single folder")
    group_backup_mode.add_argument('--day', action='store_const', const=('{:%Y-%m-%d}', '{:%Y%m%d}'), dest='bmode',
                                   help="group archies every day in single folder")
    group_zip_mode = group_backup.add_mutually_exclusive_group()
    group_zip_mode.add_argument('-z', '--gzip', action='store_const', const=('--gzip', 'tar.gz'), dest='zmode',
                                help="filter archive through gzip")
    group_zip_mode.add_argument('-j', '--bzip2', action='store_const', const=('--bzip2', 'tar.bz2'), dest='zmode',
                                help="filter archive through bzip")
    group_zip_mode.add_argument('-J', '--xz', action='store_const', const=('--xz', 'tar.xz'), dest='zmode',
                                help="filter archive through xz")
    group_lvm = parser.add_argument_group('LVM arguments')
    group_lvm.add_argument('-g', '--volume-group', required=True, dest='vgname',
                           help="volume group to backup (/dev/<vg>)")
    group_lvm.add_argument('-l', '--logical-volume', required=True, dest='lvname',
                           help="logical volume to backup (/dev/vg00/<lv>)")
    group_lvm.add_argument('-s', '--size', dest='size', default='50G',
                           help="COW snapshot volume size (50GiB)")
    group_lvm.add_argument('--snapshot-name', dest='sname', default='snapshot',
                           help="COW snapshot volume name(<>-snapshot)")
    parser.add_argument('-m', '--mount', required=True, dest='mpath',
                        help="path for mounting snapshot volume")
    parser.add_argument('-b', '--backup', required=True, dest='broot',
                        help="path to store TAR archives with")
    group_mysql = parser.add_argument_group('MySQL arguments')
    group_mysql.add_argument('--mysql-flush', action='store_true', default=False, dest='mysql_flush',
                             help="flush mysql tables with read lock before making snapshot\n"
                                  "user must have RELOAD privileges")
    group_mysql.add_argument('--mysql-user', default='flush', dest='mysql_user',
                             help="mysql user name")
    group_mysql.add_argument('--mysql-password', default='flush', dest='mysql_pass',
                             help="mysql user password")
    group_mysql.add_argument('--mysql-socket', default='/var/run/mysqld/mysqld.sock', dest='mysql_sock',
                             help="mysql unix socket")
    parser.add_argument('--keep', dest='keep',
                        help="keep folders only days")
    parser.add_argument('--log', dest='log',
                        help="log output to <log>.log and <log>_error.log")
    options = parser.parse_args()
    # set output to file
    if options.log is not None:
        sys.stdout = open("{}.log".format(options.log), mode='a', buffering=0)
        sys.stderr = open("{}_error.log".format(options.log), mode='a', buffering=0)

    options.date = datetime.now()
    options.snap = "{}_{}".format(options.lvname, options.sname)

    if not os.path.exists(options.vgname):
        options.vgname = os.path.join('/dev/', options.vgname)
        if not os.path.exists(options.vgname):
            parser.error("Can't find volume group \"{}\" !!!".format(options.vgname))
    options.vgname = os.path.normpath(options.vgname)
    if not os.path.exists(os.path.join(options.vgname, options.lvname)):
        parser.error("Can't find logical volume \"{}\" !!!".format(os.path.join(options.vgname, options.lvname)))

    options.bpath = os.path.join(options.broot, options.lvname, options.bmode[0].format(options.date))
    options.snar = "{}_{}.snar".format(options.lvname, options.bmode[1].format(options.date))

    if options.force:
        for path in (os.path.join(options.mpath, options.lvname), options.bpath):
            if not os.path.isdir(path):
                os.makedirs(path)

    if not os.path.isdir(os.path.join(options.mpath, options.lvname)):
        parser.error("Can't find mount path \"{}\"".format(os.path.join(options.mpath, options.lvname)))
    if not os.path.isdir(options.bpath):
        parser.error("Can't find backup path \"{}\"".format(options.bpath))

    fn = "{}_{}".format(options.lvname, options.bmode[1].format(options.date))
    options.topt = options.zmode[0]
    options.tar = next_file(options.bpath, fn, options.zmode[1])

    return options


def make_mysql_snapshot(options):
    """flush mysql tables with read lock, mount snapshot then release tables"""
    print "flushing db tables with read lock"
    try:
        db = MySQLdb.connect(user=options.mysql_user,
                             passwd=options.mysql_pass,
                             unix_socket=options.mysql_sock)
        try:
            cur = db.cursor()
            cur.execute("FLUSH TABLES WITH READ LOCK")
            make_snapshot(options)
            cur.execute("UNLOCK TABLES")
        finally:
            db.close()
    except Exception as Err:
        print type(Err)
        print Err.args
        print Err
        sys.exit(1)


def make_snapshot(options):
    """creat and mount COW snapshot"""
    # remove_snapshot(options)
    print "createing snapshot \"{}\" from \"{}\" ...".format(options.snap, os.path.join(options.vgname, options.lvname))
    check_call([LVCREATE_CMD, "-s", "-pr", "-L", options.size, "-n", options.snap,
                os.path.join(options.vgname, options.lvname)],
               stdout=sys.stdout, stderr=sys.stderr)

    print "mounting snapshot \"{}\" to \"{}\" ...".format(os.path.join(options.vgname, options.snap), options.mpath)
    check_call([MOUNT_CMD, "--read-only", os.path.join(options.vgname, options.snap),
                os.path.join(options.mpath, options.lvname)],
               stdout=sys.stdout, stderr=sys.stderr)


def remove_snapshot(options):
    """unmount and remove snapchot"""

    print "unounting snapshot \"{}\" from \"{}\" ...".format(os.path.join(options.vgname, options.snap), options.mpath)
    check_call([UMOUNT_CMD, os.path.join(options.vgname, options.snap)],
               stdout=sys.stdout, stderr=sys.stderr)

    print "removing snapshot \"{}\" ...".format(os.path.join(options.vgname, options.snap))
    check_call([LVREMOVE_CMD, "-f", os.path.join(options.vgname, options.snap)],
               stdout=sys.stdout, stderr=sys.stderr)


def do_tar(options):
    """create tar archive with --listed-incremental option"""

    print "creating tar \"{}\" ...".format(os.path.join(options.bpath, options.tar))
    check_call([TAR_CMD, '--create', '--verbose', '--verbose', options.topt,
                "--listed-incremental={}".format(os.path.join(options.bpath, options.snar)),
                "--file={}".format(os.path.join(options.bpath, options.tar)),
                "--directory={}".format(options.mpath),
                "--exclude={}".format(os.path.join(options.mpath, options.lvname, 'lost+found')), options.lvname],
               stdout=sys.stdout, stderr=sys.stderr)


def do_delete(options):
    """delete all folders with incremental archives created older than <options.keep> days"""

    print "check older archives"
    paths = [line[2:] for line in
             check_output([FIND_CMD, options.broot, '-ctype', 'd', '-ctime', options.keep]).splitlines()]
    pass


def do_backup(options):
    try:
        if options.mysql_flush:
            make_mysql_snapshot(options)
        else:
            make_snapshot(options)
        do_tar(options)
        if options.keep is not None:
            do_delete(options)
    finally:
        remove_snapshot(options)


if __name__ == "__main__":
    dt_start = datetime.now()
    opt = get_options()
    print "\nBegin backup: {:%Y-%m-%d %H:%M:%S}".format(dt_start)
    do_backup(opt)
    dt_end = datetime.now()
    print "Finish backup: {:%Y-%m-%d %H:%M:%S} in {}\n\n".format(dt_end, humanize.naturaldelta(dt_end - dt_start))
