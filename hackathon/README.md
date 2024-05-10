### README.md

## Features

- Competitions: Users can participate in trading competitions with specified start and end dates.
- Clans: Users can create clans, invite members, and manage their trading teams.
- Join Requests: Users can send and accept/reject join requests to join clans.
- Payout Management: Admins can approve/reject payout requests for top traders and clans.

## Installation


2. Install requirements: `pip install -r requirements.txt`
3. Run migrations: `python manage.py migrate`
4. Start the development server: `python manage.py runserver`

### API Documentation.md

# Trading Leaderboard Competition API Documentation

## Endpoints


BASE_URL= http://maindashbe-june-b18731a0e161.herokuapp.com/leaderboard/


### Competitions

#### `GET /competitions/`

Get a list of all competitions.

**Parameters:**
- None

**Response:**
```json
[
    {
        "id": 1,
        "title": "Competition 1",
        "status": "current",
        "first_prize":"1000000",
        "second_prize":"500000",
        "third_prize":"2000000"
    },
    {
        "id": 2,
        "title": "Competition 2",
        "status": "closed",
        "status": "closed",
        "first_prize":"1000000",
        "second_prize":"500000",
        "third_prize":"2000000"
    }
]
```

#### `POST /join-competition/<int:competition_id>/`

Join a competition.

**Parameters:**
- `account_number` (string, required): User's trading account number.

**Response:**
```json
{
    "detail": "Account registered successfully."
}
```

### Clans

#### `GET /clans/`

Get a list of all clans.

**Parameters:**
- None

**Response:**
```json
[
    {
        "id": 1,
        "clan_name": "Clan 1",
        "clan_admin": 1
    },
    {
        "id": 2,
        "clan_name": "Clan 2",
        "clan_admin": 2
    }
]
```

#### `POST /clans/`

Create a new clan.

**Parameters:**
- `clan_name` (string, required): Clan name.
- `community_link` (string, optional): Link to the clan's community page.
- clan_logo : image

**Response:**
```json
{
    "id": 3,
    "clan_name": "New Clan",
    "clan_admin": 3
}
```

#### `GET /clan-members/<int:clan_id>/`

Get a list of members in a clan.

**Parameters:**
- None

**Response:**
```json
[
    {
        "id": 1,
        "account_number": "12345",
        "country": "USA",
        "email": "user@example.com",
        "fullname": "John Doe"
    },
    {
        "id": 2,
        "account_number": "67890",
        "country": "UK",
        "email": "user2@example.com",
        "fullname": "Jane Smith"
    }
]
```

#### `PUT /clan-members/<int:clan_id>/`

Remove a member from a clan.

**Parameters:**
- `member_id` (int, required): ID of the member to be removed.

**Response:**
```json
{
    "detail": "Member has been successfully removed from the clan"
}
```

### Join Requests

#### `GET /join-clan/`

Get a list of all join requests.

**Parameters:**
- `clan_id` (int, optional): Filter join requests by clan ID.
Note: If thr clan_id is not provided, all the join request will come as response but if the clan_id is passed, only the request related to that clan is returned.

**Response:**
```json
[
    {
        "id": 1,
        "clan": 1,
        "user_name": "user@example.com",
        "approved": "pending"
    },
    {
        "id": 2,
        "clan": 2,
        "user_name": "user2@example.com",
        "approved": "approved"
    }
]
```

#### `POST /join-clan/`

Send a join request to a clan.

**Parameters:**
- `clan` (int, required): ID of the clan to join.

**Response:**
```json
{
    "detail": "Join request sent successfully."
}
```

#### `

### `PUT /join-clan/clan_id/?action=approved'`

The put method allows clam admin approves a users request to join
a his clan or reject the rest. The account params can be any item from this array ['approved', 'rejected'].
The approved accepts the 'request', 'rejected' rejects the the request.

**Parameters:**

None

**Response:**
```json
{
    "detail": "You have successfull left this clan."
}
```

#### `

### `PUT /leave-clan/clan_id/?action=leave`

Exist a clan.

**Parameters:**

None

**Response:**
```json
{
    "detail": "You have successfull left this clan."
}
```

<<<<<<< HEAD
#### `
=======
#### `

GET /leaderboard/
return sorted list of all accounts that are still in the competition, in descending order.

    {
                'name':'John Doe',
                'acc_size': '10000',
                'typeofaccount':'Zuma',
                'profit':800,
                'percent_24hrs':15,
                'percent_week':-2,
                'country':'Nigeria',
                'clan':'Da_boiz'
            }
>>>>>>> main
