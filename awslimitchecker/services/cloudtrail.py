"""
awslimitchecker/services/cloudtrail.py

The latest version of this package is available at:
<https://github.com/jantman/awslimitchecker>

################################################################################
Copyright 2015-2018 Jason Antman <jason@jasonantman.com>

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
Jason Antman <jason@jasonantman.com> <http://www.jasonantman.com>
################################################################################
"""

import abc  # noqa
import logging

from .base import _AwsService
from ..limit import AwsLimit

logger = logging.getLogger(__name__)


class _CloudTrailService(_AwsService):

    service_name = 'CloudTrail'
    api_name = 'cloudtrail'
    aws_type = 'AWS::CloudTrail::Trail'

    def find_usage(self):
        """
        Determine the current usage for each limit of this service,
        and update corresponding Limit via
        :py:meth:`~.AwsLimit._add_current_usage`.
        """
        logger.debug("Checking usage for service %s", self.service_name)

        self.connect()
        for lim in self.limits.values():
            lim._reset_usage()

        self._find_usage_cloudtrail()
        self._have_usage = True
        logger.debug("Done checking usage.")

    def _find_usage_cloudtrail(self):
        """Calculate current usage for CloudTrail related metrics"""

        trail_list = self.conn.describe_trails(
            includeShadowTrails=False
        )['trailList']
        trail_count = len(trail_list) if trail_list else 0

        for trail in trail_list:
            data_resource_count = 0
            if self.conn._client_config.region_name == trail['HomeRegion']:
                try:
                    response = self.conn.get_event_selectors(
                        TrailName=trail['TrailARN']
                    )
                except Exception as ex:
                    logger.debug(
                        'Unable to call GetEventSelectors on CloudTrail trail '
                        '%s: %s', trail, ex
                    )
                    continue

                event_selectors = response.get('EventSelectors', [])

                for event_selector in event_selectors:
                    data_resource_count += len(
                        event_selector.get('DataResources', [])
                    )
                self.limits['Event Selectors Per Trail']._add_current_usage(
                    len(event_selectors),
                    aws_type='AWS::CloudTrail::EventSelector',
                    resource_id=trail['Name']
                )
                self.limits['Data Resources Per Trail']._add_current_usage(
                    data_resource_count,
                    aws_type='AWS::CloudTrail::DataResource',
                    resource_id=trail['Name']
                )
            else:
                logger.debug(
                    'Ignoring event selectors and data resources for '
                    'CloudTrail %s in non-home region' % trail['Name']
                )
        self.limits['Trails Per Region']._add_current_usage(
            trail_count,
            aws_type=self.aws_type
        )

    def get_limits(self):
        """
        Return all known limits for this service, as a dict of their names
        to :py:class:`~.AwsLimit` objects.

        :returns: dict of limit names to :py:class:`~.AwsLimit` objects
        :rtype: dict
        """
        logger.debug("Gathering %s's limits from AWS", self.service_name)

        if self.limits:
            return self.limits
        limits = {}

        limits['Trails Per Region'] = AwsLimit(
            'Trails Per Region',
            self,
            5,
            self.warning_threshold,
            self.critical_threshold,
            limit_type=self.aws_type
        )

        limits['Event Selectors Per Trail'] = AwsLimit(
            'Event Selectors Per Trail',
            self,
            5,
            self.warning_threshold,
            self.critical_threshold,
            limit_type=self.aws_type,
            limit_subtype='AWS::CloudTrail::EventSelector'
        )

        limits['Data Resources Per Trail'] = AwsLimit(
            'Data Resources Per Trail',
            self,
            250,
            self.warning_threshold,
            self.critical_threshold,
            limit_type=self.aws_type,
            limit_subtype='AWS::CloudTrail::DataResource'
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
        return [
            "cloudtrail:DescribeTrails",
            "cloudtrail:GetEventSelectors",
        ]
