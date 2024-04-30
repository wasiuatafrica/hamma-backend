def split_bill(total_amount, num_people):
    """
    Splits the total bill amount equally among the given number of people.
    
    Args:
        total_amount (float): The total bill amount.
        num_people (int): The number of people to split the bill among.
        
    Returns:
        float: The amount each person should pay.
    """
    if num_people <= 0:
        raise ValueError("Number of people must be greater than 0.")
    
    return round(total_amount / num_people, 2)

def split_bill_with_shares(total_amount, shares):
    """
    Splits the total bill amount according to the provided shares.
    
    Args:
        total_amount (float): The total bill amount.
        shares (dict): A dictionary where keys are names and values are shares.
        
    Returns:
        dict: A dictionary where keys are names and values are the amounts they should pay.
    """
    total_shares = sum(shares.values())
    if total_shares == 0:
        raise ValueError("Shares cannot be all zero.")
    
    amounts = {}
    for name, share in shares.items():
        amount = round(total_amount * (share / total_shares), 2)
        amounts[name] = amount
    
    return amounts

# Example usage
total_bill = float(input("Enter the total bill amount: "))
num_people = int(input("Enter the number of people to split the bill among: "))

print(f"\nSplitting the bill equally among {num_people} people:")
equal_share = split_bill(total_bill, num_people)
print(f"Each person should pay: ${equal_share}")

print("\nSplitting the bill according to shares:")
shares = {}
while True:
    name = input("Enter a name (or 'done' to finish): ")
    if name.lower() == 'done':
        break
    share = float(input(f"Enter {name}'s share: "))
    shares[name] = share

split_amounts = split_bill_with_shares(total_bill, shares)
for name, amount in split_amounts.items():
    print(f"{name} should pay: ${amount}")