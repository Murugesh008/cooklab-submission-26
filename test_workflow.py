import requests
import json

# Query the workflow history
order_id = 'ORD-623B236D'
response = requests.get(f'http://localhost:8000/api/order/history/{order_id}')
data = response.json()

print(f'Order: {data["order_id"]}')
print(f'Status: {data["status"]}')
print('\nWorkflow Events:')
for event in data['events']:
    step_info = f' [{event["step"]}]' if event['step'] else ''
    error_info = f' | ERROR: {event["error_message"][:60]}...' if event['error_message'] else ''
    print(f'  {event["timestamp"]} - {event["event_type"]}{step_info}{error_info}')
