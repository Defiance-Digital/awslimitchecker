import logging
import requests
from awslimitchecker.alerts.base import AlertProvider
from awslimitchecker.utils import str2bool_exc

logger = logging.getLogger(__name__)


class Slack(AlertProvider):
    def __init__(self, region_name, slack_url, account_name, report_on_success="false", **kwargs):
        """
        Initialize the Slack alert provider.
        :param region_name: AWS region
        :param slack_url: Slack webhook URL
        :param account_name: AWS account name
        :param report_on_success: If true, sends a success notification message to Slack. Otherwise, no message is sent.
        """
        super().__init__(region_name)

        if not slack_url:
            raise ValueError("Slack URL is required but was not provided.")

        self.slack_url = slack_url
        self.report_on_success = str2bool_exc(report_on_success)
        self.account_name = account_name
        self.warning_threshold = int(kwargs.get("warning_threshold", 80))
        self.critical_threshold = int(kwargs.get("critical_threshold", 90))

    def build_block_kit_table(self, headers, rows):
        blocks = []

        for row in rows:
            row_block = {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*{headers[0]}:*"},  # Service Limit
                    {"type": "mrkdwn", "text": f"{row[0]}"},
                    {"type": "mrkdwn", "text": f"*{headers[1]}:*"},  # Resource
                    {"type": "mrkdwn", "text": f"{row[1]}"},
                    {"type": "mrkdwn", "text": f"*{headers[2]}:*"},  # Usage #
                    {"type": "mrkdwn", "text": f"{row[2]}"},
                    {"type": "mrkdwn", "text": f"*{headers[3]}:*"},  # Usage %
                    {"type": "mrkdwn", "text": f"{row[3]}"},
                    {"type": "mrkdwn", "text": f"*{headers[4]}:*"},  # Limit
                    {"type": "mrkdwn", "text": f"{row[4]}"}
                ]
            }

            blocks.append(row_block)

            blocks.append({"type": "divider"})

        return blocks

    def send_to_slack(self, payload):
        slack_data = {
            "text": "AWS Limit Check Results",
            "blocks": [
                          {
                              "type": "section",
                              "text": {
                                  "type": "mrkdwn",
                                  "text": "*AWS Limit Check Results*"
                              }
                          },
                          {
                              "type": "section",
                              "text": {
                                  "type": "mrkdwn",
                                  "text": self.account_name
                              }
                          },
                      ] + payload
        }

        headers = {'Content-Type': 'application/json'}

        try:
            response = requests.post(self.slack_url, json=slack_data, headers=headers)
            response.raise_for_status()
            logger.info("Message posted successfully to Slack.")
        except requests.exceptions.HTTPError as err:
            logger.error(f"Failed to post message to Slack: {err}")
        except requests.exceptions.RequestException as e:
            logger.error(f"An error occurred while sending the request to Slack: {e}")

    # Helper function to build Slack blocks and send the message
    def format_and_send(self, problems):
        if not isinstance(problems, dict):
            logger.error(problems)

        headers = ['Service Limit', 'Resource', 'Usage #', 'Usage %', 'Limit']
        table = []

        for svc, limits in problems.items():
            for limit_name, limit in limits.items():
                for usage in limit.get_current_usage():
                    resource = usage.resource_id or '-'
                    limit_value = limit.quotas_limit or "<unknown>"
                    use_value = usage.value
                    usage_percentage = (use_value / limit_value) * 100 if isinstance(limit_value, (int, float)) else "-"

                    # Determine the emoji based on usage percentage and thresholds
                    emoji = ""
                    if isinstance(usage_percentage, float):
                        if usage_percentage >= self.critical_threshold:
                            emoji = ":this-is-fine-fire:"
                        elif usage_percentage >= self.warning_threshold:
                            emoji = " :warning:"

                    # Create a row for the Slack message
                    table.append([
                        f"{svc}/{limit_name}",
                        resource,
                        str(use_value),
                        f"{usage_percentage:.0f} % {emoji}" if isinstance(usage_percentage, float) else "-",
                        str(limit_value)
                    ])

        # Build Slack blocks and send the message
        blocks = self.build_block_kit_table(headers, table)
        self.send_to_slack(blocks)

    def on_critical(self, problems, problem_str, exc=None, duration=None):
        message = f"CRITICAL: Service quota breached.'. Issues: {problem_str}. Duration: {duration:.2f} seconds."
        logger.critical(message)
        self.format_and_send(problems)

    def on_warning(self, problems, problem_str, duration=None):
        message = f"WARNING: Warning threshold exceeded.'. Issues: {problem_str}. Duration: {duration:.2f} seconds."
        logger.warning(message)
        self.format_and_send(problems)

    def on_success(self, duration=None):
        message = f"Scan completed successfully in {duration:.2f} seconds."
        logger.info(message)

        if self.report_on_success:
            self.send_to_slack([
                {"type": "section", "text": {"type": "mrkdwn", "text": message}},
                {"type": "divider"}
            ])

