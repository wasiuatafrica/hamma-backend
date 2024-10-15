from sendgrid import SendGridAPIClient
from datetime import datetime, timedelta
import os

# Set your SendGrid API key
sg = SendGridAPIClient(
    "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"
)

# # Set the date range for which you want to retrieve data
# end_date = datetime.now()
# start_date = end_date - timedelta(days=1)  # Last 30 days

# # Get all emails
# # response = sg.client.stats.get(
# #     query_params={
# #         "start_date": start_date.date().isoformat(),
# #         "end_date": end_date.date().isoformat(),
# #         "aggregated_by": "day",
# #     }
# # )

# # print("Email Statistics:")
# # print(response.body)

# # Get number of opens
# response = sg.client.stats.get(
#     query_params={
#         "start_date": start_date.date().isoformat(),
#         "end_date": end_date.date().isoformat(),
#         "aggregated_by": "day",
#         "metrics": "opens",
#     }
# )

# print("\nOpen Statistics:")
# print(response.body)

# # To get unique opens, you can use the 'unique_opens' metric instead of 'opens'

from sendgrid import SendGridAPIClient
import os
import json
from datetime import datetime, timedelta


# The email address you want to search for
email_to_search = "nwaforglory6@gmail.com"

# The subject line of the email you're looking for (optional)
subject_to_search = "Test track mail"

# Set the date range for which you want to retrieve data
end_date = datetime.now()
start_date = end_date - timedelta(days=30)  # Last 30 days

try:
    # Make the API call
    response = sg.client.messages.search.post(
        request_body={
            "query": f'to_email:"{email_to_search}" AND subject:"{subject_to_search}"',
            "start_date": start_date.date().isoformat(),
            "end_date": end_date.date().isoformat(),
            "limit": 1,  # Adjust this if you expect multiple matches
        }
    )

    # Parse the response
    data = json.loads(response.body)

    if data["messages"]:
        email = data["messages"][0]
        print(f"Email found:")
        print(f"Subject: {email['subject']}")
        print(f"Sent at: {email['last_event_time']}")
        print(f"Status: {email['status']}")
        if "opens" in email:
            print(f"Opens: {len(email['opens'])}")
            print(f"First opened at: {email['opens'][0]['opened']}")
        else:
            print("This email has not been opened yet.")
    else:
        print("No matching emails found.")

except Exception as e:
    print(f"An error occurred: {e}")
