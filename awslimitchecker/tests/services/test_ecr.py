"""
awslimitchecker/tests/services/test_ecr.py

The latest version of this package is available at:
<https://github.com/Defiance-Digital/awslimitchecker>

################################################################################
Copyright 2015-2025 Jason Antman <jason@jasonantman.com>

    This file is part of awslimitchecker, also known as awslimitchecker.

    awslimitchecker is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    awslimitchecker is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU Affero General Public License for more details.

    You should have received a copy of the GNU Affero General Public License
    along with awslimitchecker.  If not, see <http://www.gnu.org/licenses/>.

The Copyright and Authors attributions contained herein may not be removed or
otherwise altered, except to add the Author attribution of a contributor to
this work. (Additional Terms pursuant to Section 7b of the AGPL v3)
################################################################################
While not legally required, I sincerely request that anyone who finds
bugs please submit them at <https://github.com/jantman/awslimitchecker> or
to me via email, and that you send any contributions or improvements
either as a pull request on GitHub, or to me via email.
################################################################################

AUTHORS:
Mike Gray <michael.gray@defiance.ai> <https://defiancedigital.com>
################################################################################
"""

import sys
from awslimitchecker.tests.services import result_fixtures
from awslimitchecker.services.ecr import _EcrService

# https://code.google.com/p/mock/issues/detail?id=249
# py>=3.4 should use unittest.mock not the mock package on pypi
if sys.version_info[0] < 3 or sys.version_info[0] == 3 and sys.version_info[1] < 4:
    from mock import patch, call, Mock
else:
    from unittest.mock import patch, call, Mock

pbm = "awslimitchecker.services.ecr"  # module patch base
pb = "%s._EcrService" % pbm  # class patch pase


class Test_EcrService(object):

    def test_init(self):
        """test __init__()"""
        cls = _EcrService(21, 43, {}, None)
        assert cls.service_name == "ECR"
        assert cls.api_name == "ecr"
        assert cls.conn is None
        assert cls.warning_threshold == 21
        assert cls.critical_threshold == 43

    def test_get_limits(self):
        """Test get_limits"""
        cls = _EcrService(21, 43, {}, None)
        cls.limits = {}
        res = cls.get_limits()
        assert sorted(res.keys()) == sorted(["Images per repository"])
        limit = res["Images per repository"]
        assert limit.service == cls
        assert limit.def_warning_threshold == 21
        assert limit.def_critical_threshold == 43
        assert limit.default_limit == 10000
        assert limit.limit_type == "AWS::ECR::Repository"

    def test_get_limits_again(self):
        """test that existing limits dict is returned on subsequent calls"""
        mock_limits = Mock()
        cls = _EcrService(21, 43, {}, None)
        cls.limits = mock_limits
        res = cls.get_limits()
        assert res == mock_limits

    def test_find_usage(self):
        """Test find_usage"""
        mock_conn = Mock()

        repos_resp = {
            "repositories": [
                {
                    "repositoryName": "repo1",
                    "repositoryArn": "arn:aws:ecr:region:account:repository/repo1",
                },
                {
                    "repositoryName": "repo2",
                    "repositoryArn": "arn:aws:ecr:region:account:repository/repo2",
                },
            ]
        }

        images_resp1 = {
            "imageDetails": [
                {"imageDigest": "sha256:1234"},
                {"imageDigest": "sha256:5678"},
            ]
        }

        images_resp2 = {
            "imageDetails": [
                {"imageDigest": "sha256:abcd"},
                {"imageDigest": "sha256:efgh"},
                {"imageDigest": "sha256:ijkl"},
            ]
        }

        mock_conn.describe_repositories.return_value = repos_resp

        def mock_describe_images(**kwargs):
            if kwargs["repositoryName"] == "repo1":
                return images_resp1
            return images_resp2

        mock_conn.describe_images.side_effect = mock_describe_images

        with patch("%s.connect" % pb) as mock_connect:
            with patch("%s.paginate_dict" % pbm) as mock_paginate:
                mock_paginate.side_effect = [repos_resp, images_resp1, images_resp2]

                cls = _EcrService(21, 43, {}, None)
                cls.conn = mock_conn
                assert cls._have_usage is False
                cls.find_usage()

        mock_connect.assert_any_call()
        assert cls._have_usage is True

        # Check usage
        usage = cls.limits["Images per repository"].get_current_usage()
        assert len(usage) == 2
        assert usage[0].get_value() == 2  # repo1
        assert usage[0].resource_id == "repo1"
        assert usage[1].get_value() == 3  # repo2
        assert usage[1].resource_id == "repo2"

    def test_required_iam_permissions(self):
        """Test required_iam_permissions"""
        cls = _EcrService(21, 43, {}, None)
        assert sorted(cls.required_iam_permissions()) == sorted(
            ["ecr:DescribeRepositories", "ecr:DescribeImages"]
        )
