def example_function():
    i = 0
    while i < 5:
        print(i)
        if i == 3:
            return  # Exit the function when i is 3
        i += 1

    print("This will not be executed")

# Call the function
example_function()
