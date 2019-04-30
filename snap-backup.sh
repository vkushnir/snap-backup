#!/bin/bash
#
# Dayly backup files with LVM Snapshot
#
# PARAMS:
#  -z <0|1> Full backup 1 - yearly, 0 - monthly
#  -v <Logical Volume Name>
#  -g <Volume Group>
#  -m <Mount Path>
#  -b <Backup Path>
#  -s <Snapshot Size>

#Set a default values for variables
# bmode: backup mode <0|1>
bmode=0
# lvname: logical volume name
# vgpath: volume group
# mpath: mount path
# bpath: backup path
bpath='/backup/'
# ssize: snapshot size
ssize='50GiB'

self=$(basename $0)
self_cfg=${self%.*}.cfg
if [ -s ${self_cfg} ]; then
  source ${self_cfg}
else
  if [ -s /etc/${self_cfg} ]; then
    source /etc/${self_cfg}
  fi
fi

opt="--create --verbose --verbose --bzip2"

Y=`date +%Y`
M=`date +%m`
D=`date +%d`

#Process the arguments 
while getopts z:v:g:m:b:s: opt; do
  case "$opt" in
    z) bmode=${OPTARG};;
    v) lvname=${OPTARG};;
    g) vgpath="/dev/${OPTARG}";;
    m) mpath=${OPTARG%%/};;
    b) bpath=${OPTARG%%/};;
    s) ssize=${OPTARG};;
  esac
done

if (( $bmode )) ; then date="${Y}"; else date="${Y}-${M}"; fi
day="${Y}${M}${D}"

bpath="${bpath}/${lvname}/${date}"
snar="${lvname}_${date}.snar"
tar="${lvname}_${day}.tar.bz2"
snap="${lvname}-snapshot"

echo -e "\nCreateing snapshot \"${snap}\" from \"${vgpath}/${lvname}\" ..."
lvcreate -s -p r -L $ssize -n $snap ${vgpath}/${lvname}
RETVAL=$?
if [ $RETVAL -ne 0 ]; then
  echo "Create snapshot FAILED!!!"
  exit $RETVAL
fi

echo -e "\nMounting \"${vgpath}/${snap}\" in to \"${mpath}/${lvname}\" ..."
mkdir -p ${mpath}/${lvname}
mount -o ro ${vgpath}/${snap} ${mpath}/${lvname}
RETVAL=$?
if [ $RETVAL -ne 0 ]; then
  echo "Mount snapshot FAILED!!!"
  exit $RETVAL
fi

echo -e "\nBackup files from \"${mpath}/${lvname}\" to \"${bpath}/${tar}\" ..."
mkdir -p $bpath
tar --create --verbose --verbose --bzip2 --listed-incremental="${bpath}/${snar}" --file="${bpath}/${tar}" --directory="${mpath}" --exclude="${mpath}/${lvname}/lost+found" "${lvname}"
RETVAL=$?
if [ $RETVAL -ne 0 ]; then
  echo "Backap FAILED!!!"
  exit $RETVAL
fi

echo -e "\nUnounting \"${vgpath}/${snap}\" ..."
umount ${vgpath}/${snap}
RETVAL=$?
if [ $RETVAL -ne 0 ]; then
  echo "Unmount FAILED!!!"
  exit $RETVAL
fi

echo -e "\nRemoving snapshot \"${vgpath}/${snap}\" ..."
lvremove -f ${vgpath}/${snap}
if [ $RETVAL -ne 0 ]; then
  echo "Remove snapshot FAILED!!!"
  exit $RETVAL
fi

