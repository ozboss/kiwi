# Copyright (c) 2015 SUSE Linux GmbH.  All rights reserved.
#
# This file is part of kiwi.
#
# kiwi is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# kiwi is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with kiwi.  If not, see <http://www.gnu.org/licenses/>
#
import logging
from typing import List

# project
from kiwi.utils.temporary import Temporary
from kiwi.command import Command
from kiwi.partitioner.base import PartitionerBase

from kiwi.exceptions import (
    KiwiPartitionerMsDosFlagError
)

log = logging.getLogger('kiwi')


class PartitionerMsDos(PartitionerBase):
    """
    **Implement old style msdos partition setup**
    """
    def post_init(self) -> None:
        """
        Post initialization method

        Setup sfdisk partition type/flag map
        """
        self.flag_map = {
            'f.active': True,
            't.linux': '83',
            't.swap': '82',
            't.lvm': '8e',
            't.raid': 'fd',
            't.efi': None,
            't.csm': None,
            't.prep': '41',
            't.extended': '5'
        }

    def create(
        self, name: str, mbsize: int, type_name: str, flags: List[str] = []
    ) -> None:
        """
        Create msdos partition

        :param string name: partition name
        :param int mbsize: partition size
        :param string type_name: partition type
        :param list flags: additional flags
        """
        if self.extended_layout:
            if self.partition_id < 3:
                # in primary boundary
                self._create_primary(name, mbsize, type_name, flags)
            elif self.partition_id == 3:
                # at primary boundary, create extended + logical
                self._create_extended(name)
                self._create_logical(name, mbsize, type_name, flags)
            elif self.partition_id > 3:
                # in logical boundary
                self._create_logical(name, mbsize, type_name, flags)
        else:
            self._create_primary(name, mbsize, type_name, flags)

    def set_flag(self, partition_id: int, flag_name: str) -> None:
        """
        Set msdos partition flag

        :param int partition_id: partition number
        :param string flag_name: name from flag map
        """
        if flag_name not in self.flag_map:
            raise KiwiPartitionerMsDosFlagError(
                'Unknown partition flag %s' % flag_name
            )
        if self.flag_map[flag_name]:
            if flag_name == 'f.active':
                Command.run(
                    [
                        'parted', self.disk_device,
                        'set', format(partition_id), 'boot', 'on'
                    ]
                )
            else:
                Command.run(
                    [
                        'sfdisk', '-c', self.disk_device,
                        format(partition_id), self.flag_map[flag_name]
                    ]
                )
        else:
            log.warning('Flag %s ignored on msdos', flag_name)

    def resize_table(self, entries: int = None) -> None:
        """
        Resize partition table

        Nothing to be done here for msdos table

        :param int entries: unused
        """
        pass

    def _create_primary(
        self, name: str, mbsize: int, type_name: str, flags: List[str] = []
    ) -> None:
        """
        Create primary msdos partition
        """
        self.partition_id += 1
        fdisk_input = Temporary().new_file()
        if self.partition_id > 1:
            # Undefined start sector value skips this for fdisk and
            # use its default value
            self.start_sector = None
        with open(fdisk_input.name, 'w') as partition:
            log.debug(
                '%s: fdisk: n p %d cur_position +%sM w q',
                name, self.partition_id, format(mbsize)
            )
            partition.write(
                'n\np\n{0}\n{1}\n{2}\nw\nq\n'.format(
                    self.partition_id,
                    '' if not self.start_sector else self.start_sector,
                    '' if mbsize == 'all_free' else '+{0}M'.format(mbsize)
                )
            )
        self._call_fdisk(fdisk_input.name)
        self._set_all_flags(type_name, flags)

    def _create_extended(self, name: str) -> None:
        """
        Create extended msdos partition
        """
        self.partition_id += 1
        fdisk_input = Temporary().new_file()
        with open(fdisk_input.name, 'w') as partition:
            log.debug(
                '%s: fdisk: n e %d cur_position +all_freeM w q',
                name, self.partition_id
            )
            partition.write(
                'n\ne\n{0}\n{1}\n{2}\nw\nq\n'.format(
                    self.partition_id, '', ''
                )
            )
        self._call_fdisk(fdisk_input.name)

    def _create_logical(
        self, name: str, mbsize: int, type_name: str, flags: List[str] = []
    ) -> None:
        """
        Create logical msdos partition
        """
        self.partition_id += 1
        fdisk_input = Temporary().new_file()
        with open(fdisk_input.name, 'w') as partition:
            log.debug(
                '%s: fdisk: n %d cur_position +%sM w q',
                name, self.partition_id, format(mbsize)
            )
            partition.write(
                'n\n{0}\n{1}\n{2}\nw\nq\n'.format(
                    self.partition_id,
                    '',
                    '' if mbsize == 'all_free' else '+{0}M'.format(mbsize)
                )
            )
        self._call_fdisk(fdisk_input.name)
        self._set_all_flags(type_name, flags)

    def _set_all_flags(self, type_name: str, flags: List[str]) -> None:
        self.set_flag(self.partition_id, type_name)
        if flags:
            for flag_name in flags:
                self.set_flag(self.partition_id, flag_name)

    def _call_fdisk(self, fdisk_config_file_path: str) -> None:
        bash_command = ' '.join(
            ['cat', fdisk_config_file_path, '|', 'fdisk', self.disk_device]
        )
        try:
            Command.run(
                ['bash', '-c', bash_command]
            )
        except Exception:
            # unfortunately fdisk reports that it can't read in the partition
            # table which I consider a bug in fdisk. However the table was
            # correctly created and therefore we continue. Problem is that we
            # are not able to detect real errors with the fdisk operation at
            # that point.
            log.debug('potential fdisk errors were ignored')
