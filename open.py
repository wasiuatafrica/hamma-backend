from openai import OpenAI
client = OpenAI(api_key="")

model = '''
class Alert(auto_prefetch.Model):
    user= auto_prefetch.ForeignKey(User,on_delete=models.CASCADE)
    stock= auto_prefetch.ForeignKey(Stock,on_delete=models.CASCADE)
    alert_name=models.CharField(max_length=50)
    description=models.TextField(default="")
    alert_type=models.CharField(max_length=30, choices=(("price", "price"), ("volume", "volume")), default='price')
    action=models.CharField(max_length=50, choices=(("above", "above"), ("below", "below")))
    to_price=models.FloatField(blank=True, null=True)
    to_volume=models.FloatField(blank=True, null=True)    
    frequency=models.CharField(max_length=50, choices=(("Once","Once"),("Everytime", "Everytime")))
    expire = models.DateTimeField(default=datetime.now() +timedelta(weeks=7))
    
'''
# prompt = '''
# notify me for ZENITHBANK stock everytime the volume goes below 9320 before 7 january 2024 3pm
# '''
prompt = '''
alert me everytime WEMABANK price goes below 93.20 before 7 january 2024 3pm
'''

response = client.chat.completions.create(
  model="gpt-3.5-turbo",
  messages=[
    {"role": "system", "content": "You are a helpful django software development assistant helping in creating a trading app alert system."},
    {"role": "user", "content": f'''i want to extract parameters from {prompt} to create djano model {model} can you 
        extract the needed parameter in python dictionary  format only as the response, the expected dict keys are stock,alert_type,action,expire,to_price or to_volume and frequency.
        dont write write any explanation before or after the dictionary, i only want the dictionary as response'''}
  ]
)


print(response)
# print(response['choices'][0]['message']['content'])
print(response.choices[0].message.content)