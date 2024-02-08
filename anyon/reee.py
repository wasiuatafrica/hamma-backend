from datetime import datetime

def get_quarter(date_str):
    try:
        # Convert the input string to a datetime object
        date_object = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S")
        
        # Extract the quarter from the datetime object
        quarter = (date_object.month - 1) // 3 + 1
        
        return quarter
    except ValueError:
        # Handle invalid date format
        return "Invalid date format"

# Example usage
date_str = "2024-12-01T00:00:00"
result = get_quarter(date_str)

if isinstance(result, int):
    print(f"The quarter for {date_str} is {result}")
else:
    print(result)
