Search for businesses, services, or shops in a specific city.

Use this tool ONLY when:
1. The user explicitly asks for a specific service (e.g. 'find a car mechanic', 'where is a bakery?', 'تعویض روغنی میخوام').
2. You have successfully identified the 'category_id' from the system prompt list.

Do NOT use this tool if:
1. The user is just saying hello or asking general questions.
2. The requested service does not match any ID in the list.

Parameters:
- category_id: The numeric ID from the provided list.
- city_name: The target city name in Persian. YOU MUST DETERMINE THIS:
    1. If the user explicitly mentioned a city in their message (e.g. "in Tehran"), use that city.
    2. If the user did NOT mention a city, look at the "[User Location Info]" in the system prompt and use that city name.
    3. If neither is available, DO NOT call this tool; ask the user for their city instead.