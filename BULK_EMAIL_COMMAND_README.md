# Bulk Email Django Management Command

## Overview
This Django management command allows you to send bulk emails to valid users in your database while excluding unsubscribed users and invalid email addresses.

## File Location
`accounts/management/commands/send_bulk_email.py`

## Features
- ✅ Excludes unsubscribed users (from `Unsubscribe` model)
- ✅ Filters out invalid email domains
- ✅ Excludes test emails
- ✅ Excludes inactive users
- ✅ Supports dry-run mode for testing
- ✅ Configurable email template and subject
- ✅ Confirmation prompt before sending
- ✅ Detailed progress and error reporting
- ✅ Optional limit for testing
- ✅ Easy to customize - just edit the command file

## Usage

### Step 1: Edit the Configuration
Open `accounts/management/commands/send_bulk_email.py` and edit the configuration section (around line 67):

```python
# ==================== CONFIGURATION ====================
# Edit these settings as needed

template_name = "general/sample_email.html"  # Path to your email template
subject = "Important Update from Hamma"  # Email subject
from_email = "Hamma Team <teamgohamma@gmail.com>"  # Sender email

# Testing options
dry_run = False  # Set to True to test without sending emails
limit = None  # Set to a number (e.g., 10) to limit emails sent

# ======================================================
```

### Step 2: Run the Command
```bash
python manage.py send_bulk_email
```

That's it! No command-line arguments needed.

## Configuration Examples

### Example 1: Dry Run Test
```python
template_name = "general/sample_email.html"
subject = "Test Newsletter"
from_email = "Hamma Team <teamgohamma@gmail.com>"
dry_run = True  # ← Won't send any emails
limit = None
```

### Example 2: Test with Limited Users
```python
template_name = "prop/welcome_hamma_prop.html"
subject = "Welcome to Hamma Prop"
from_email = "Hamma Prop Team <prop@hamma.trade>"
dry_run = False
limit = 10  # ← Send to only 10 users
```

### Example 3: Full Production Send
```python
template_name = "general/monthly_newsletter.html"
subject = "Monthly Newsletter - October 2025"
from_email = "Hamma Team <teamgohamma@gmail.com>"
dry_run = False
limit = None  # ← Send to all valid users
```

## Email Template

### Available Context Variables
When creating your email template, you have access to these variables:

```django
{{ firstname }}  - User's first name (capitalized)
{{ date }}       - Current date
{{ email }}      - User's email address
```

### Sample Template
A sample template is provided at `templates/general/sample_email.html`.

### Using Existing Templates
You can use any existing template in the `templates/` directory:
- `prop/welcome_hamma_prop.html`
- `general/WIthdrawalRequesReceived.html`
- `general/depositRecieptApproved.html`
- etc.

## Email Filtering

The command automatically excludes:

1. **Unsubscribed Users**: Users in the `Unsubscribe` model
2. **Inactive Users**: Users with `is_active=False`
3. **Test Emails**: Emails containing "@test"
4. **Invalid Domains**: Common temporary/fake email domains like:
   - example.com
   - test.com
   - mailinator.com
   - tempmail.com
   - 10minutemail.com
   - yopmail.com
   - etc.
5. **Short Domains**: Email addresses with very short domains (e.g., @xx.com)
6. **Missing Data**: Users without email or firstname


## Workflow Example

### 1. Test with Dry Run
Edit the command file and set:
```python
dry_run = True
limit = None
```

Then run:
```bash
python manage.py send_bulk_email
```

This will show you:
- How many users will receive the email
- Sample of first 5 users
- No emails are actually sent

### 2. Test with Limited Send
Edit the command file and set:
```python
dry_run = False
limit = 5
```

Then run:
```bash
python manage.py send_bulk_email
```

This sends to only 5 users for verification.

### 3. Full Send
Edit the command file and set:
```python
dry_run = False
limit = None
template_name = "general/monthly_newsletter.html"
subject = "Monthly Newsletter - October 2025"
```

Then run:
```bash
python manage.py send_bulk_email
```

The command will:
1. Show you statistics about recipients
2. Ask for confirmation (type 'yes' to continue)
3. Send emails with progress updates
4. Display summary of sent/failed emails


## Output Examples

### Dry Run Output
```
Unsubscribed users: 45
Manually exempted users: 0

Total valid users to email: 1,234

=== DRY RUN MODE - No emails will be sent ===

Sample users that would receive emails:
  1. john@example.com - John
  2. jane@example.com - Jane
  3. bob@example.com - Bob
  4. alice@example.com - Alice
  5. charlie@example.com - Charlie
  ... and 1,229 more users
```

### Actual Send Output
```
Unsubscribed users: 45
Manually exempted users: 0

Total valid users to email: 1,234

You are about to send 1,234 emails.
Template: general/sample_email.html
Subject: Monthly Newsletter - October 2025
From: Hamma Team <teamgohamma@gmail.com>

Type 'yes' to continue: yes

Sending to: john@example.com (John)
Sending to: jane@example.com (Jane)
...
==================================================
✓ Successfully sent: 1,234
==================================================
```

## Adding Manual Exemptions

To manually exempt specific users, edit the command file and add emails to the `exempted_users` list:

```python
# In send_bulk_email.py, line ~89
exempted_users = [
    "admin@hamma.trade",
    "test@hamma.trade",
    # Add more emails here
]
```

## Troubleshooting

### Email Not Sending
- Check SENDGRID_API_KEY is set in environment variables
- Verify the template path is correct
- Check Django settings for email configuration

### Users Not Receiving
- Verify user has `is_active=True`
- Check user is not in `Unsubscribe` model
- Ensure email doesn't match any filter criteria

### Template Errors
- Ensure template exists in `templates/` directory
- Check template syntax is valid Django template
- Verify context variables are used correctly

## Best Practices

1. **Always test first**: Use `--dry-run` before sending to all users
2. **Test with limit**: Use `--limit 10` to test actual sending
3. **Use descriptive subjects**: Make it clear what the email is about
4. **Track campaigns**: Consider logging sent emails to a tracking model
5. **Time your sends**: Send during appropriate hours for your audience
6. **Monitor bounces**: Keep track of failed sends

## Related Models

### CustomUser (accounts.models)
- `email`: User's email address
- `firstname`: User's first name
- `is_active`: Whether user account is active

### Unsubscribe (accounts.models)
- `email`: Unsubscribed email address
- `created`: When user unsubscribed

## Support

For issues or questions, contact the development team or check the project documentation.
