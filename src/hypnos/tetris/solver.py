import requests

cookies = {
    'auth_token': 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI1NSIsImV4cCI6MTc2OTUxNzIzOSwidHlwZSI6ImFjY2VzcyIsImlhdCI6MTc2ODMwNzYzOSwianRpIjoiWHl1elU0QkZUWmc4VWpOalhnN3NkWUJ1UzZhUDdGT0g4U3hRVU1UenY0YyJ9.7JAXicQXnkpj0fZ7WbEaOgzhD6NZgAj1HVvG6io4snI',
    'csrf_token': 'aeezgMQUk1L4nX6GyMd82ChT6HuqFdYq7dwN8l58c7Q',
}

headers = {
    'accept': '*/*',
    'accept-language': 'fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7',
    'content-type': 'application/json',
    'origin': 'https://play.hypnos2026.fr',
    'priority': 'u=1, i',
    'referer': 'https://play.hypnos2026.fr/game/tetris/',
    'sec-ch-ua': '"Google Chrome";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'same-origin',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36',
    'x-csrf-token': 'aeezgMQUk1L4nX6GyMd82ChT6HuqFdYq7dwN8l58c7Q',
    # 'cookie': 'auth_token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI1NSIsImV4cCI6MTc2OTUxNzIzOSwidHlwZSI6ImFjY2VzcyIsImlhdCI6MTc2ODMwNzYzOSwianRpIjoiWHl1elU0QkZUWmc4VWpOalhnN3NkWUJ1UzZhUDdGT0g4U3hRVU1UenY0YyJ9.7JAXicQXnkpj0fZ7WbEaOgzhD6NZgAj1HVvG6io4snI; csrf_token=aeezgMQUk1L4nX6GyMd82ChT6HuqFdYq7dwN8l58c7Q',
}

json_data = {
    'score': 100000,
    'completion_time': 582,
    'data': {
        'level': 6,
        'lines': -50,
        'raw_score': 3e10,
    },
}

response = requests.post(
    'https://play.hypnos2026.fr/api/arg/challenges/1052274132/submit',
    cookies=cookies,
    headers=headers,
    json=json_data,
)


print(response.json())
print(response.status_code)

# Note: json_data will not be serialized by requests
# exactly as it was in the original request.
#data = '{"score":700,"completion_time":166,"data":{"level":1,"lines":7,"raw_score":700}}'
#response = requests.post(
#    'https://play.hypnos2026.fr/api/arg/challenges/1052274132/submit',
#    cookies=cookies,
#    headers=headers,
#    data=data,
#)