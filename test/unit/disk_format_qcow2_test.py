from nose.tools import *
from mock import patch

import mock

import nose_helper

from kiwi.exceptions import *
from kiwi.disk_format_qcow2 import DiskFormatQcow2


class TestDiskFormatQcow2(object):
    def setup(self):
        xml_data = mock.Mock()
        xml_data.get_name = mock.Mock(
            return_value='some-disk-image'
        )
        self.xml_state = mock.Mock()
        self.xml_state.xml_data = xml_data
        self.disk_format = DiskFormatQcow2(
            self.xml_state, 'root_dir', 'target_dir'
        )

    def test_post_init(self):
        self.disk_format.post_init({'option': 'value'})
        assert self.disk_format.options == ['-o', 'option', 'value']

    @patch('kiwi.disk_format_qcow2.Command.run')
    def test_create_image_format(self, mock_command):
        self.disk_format.create_image_format()
        mock_command.assert_called_once_with(
            [
                'qemu-img', 'convert', '-c', '-f', 'raw',
                'target_dir/some-disk-image.raw', '-O', 'qcow2',
                'target_dir/some-disk-image.qcow2'
            ]
        )
