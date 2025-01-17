"""
awslimitchecker/services/ecr.py

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

import abc  # noqa
import logging
from typing import Dict

from .base import _AwsService
from ..limit import AwsLimit
from ..utils import paginate_dict

logger = logging.getLogger(__name__)


class _EcrService(_AwsService):

    service_name = "ECR"
    api_name = "ecr"  # AWS API name to connect to (boto3.client)
    quotas_service_code = "ecr"  # "L-03A36CE1"

    def find_usage(self):
        """
        Determine the current usage for each limit of this service,
        and update corresponding Limit via _add_current_usage().
        """
        logger.debug("Checking usage for service %s", self.service_name)
        self.connect()
        for lim in self.limits.values():
            lim._reset_usage()

        # Get list of all repositories
        try:
            repositories = paginate_dict(
                self.conn.describe_repositories,
                alc_marker_path=["nextToken"],
                alc_data_path=["repositories"],
                alc_marker_param="nextToken",
            )

            # For each repository, get the image count
            repos = []
            if isinstance(repositories, dict):
                repos = repositories.get("repositories", [])
            if isinstance(repositories, list):
                repos = repositories
            for repo in repos:
                repo_name = repo["repositoryName"]
                # Get image details for the repository
                images = paginate_dict(
                    self.conn.describe_images,
                    repositoryName=repo_name,
                    alc_marker_path=["nextToken"],
                    alc_data_path=["imageDetails"],
                    alc_marker_param="nextToken",
                )
                # Add usage for this repository
                self.limits["Images per repository"]._add_current_usage(
                    len(images.get("imageDetails", [])),
                    aws_type="AWS::ECR::Repository",
                    resource_id=repo_name,
                )

            self._have_usage = True
            logger.debug("Done checking usage.")
        except Exception as e:
            logger.exception("Error getting ECR usage: %s", e)

    def get_limits(self) -> Dict[str, AwsLimit]:
        """
        Return all known limits for this service, as a dict of their names
        to AwsLimit objects.

        :returns: dict of limit names to AwsLimit objects
        :rtype: dict
        """
        if self.limits != {}:
            return self.limits

        limits = {}
        limits["Images per repository"] = AwsLimit(
            name="Images per repository",
            service=self,
            default_limit=10000,  # default soft limit
            def_warning_threshold=self.warning_threshold,
            def_critical_threshold=self.critical_threshold,
            limit_type="AWS::ECR::Repository",
        )

        self.limits = limits
        return limits

    def required_iam_permissions(self):
        """
        Return a list of IAM Actions required for this Service to function
        properly. All Actions will be shown with an Effect of "Allow"
        and a Resource of "*".

        :returns: list of IAM Action strings
        :rtype: list
        """
        return ["ecr:DescribeRepositories", "ecr:DescribeImages"]
