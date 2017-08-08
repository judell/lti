# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import pytest

from lti.config import (
    SettingError,
    configure,
)


@pytest.mark.usefixtures('env_setting')
class TestConfigure(object):

    def test_it_raises_if_env_setting_raises(self, env_setting):
        env_setting.side_effect = SettingError()

        with pytest.raises(SettingError):
            configure()

    def test_it_returns_a_Configurator_with_all_the_settings(self,
                                                             env_setting):
        def env_setting_side_effect(envvar_name):
            return {
                'LTI_SERVER': 'the_lti_server_setting',
                'LTI_CREDENTIALS_URL':  'the_lti_credentials_url_setting',
            }[envvar_name]

        env_setting.side_effect = env_setting_side_effect

        config = configure()

        assert config.registry.settings['lti_server'] == 'the_lti_server_setting'
        assert config.registry.settings['lti_credentials_url'] == 'the_lti_credentials_url_setting'

    @pytest.fixture
    def env_setting(self, patch):
        return patch('lti.config.env_setting')
