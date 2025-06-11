# Restaurant Recommendation API

A FastAPI-based restaurant recommendation system that provides personalized menu suggestions based on category and price range filters.

## Features

- **Smart Recommendations**: Uses a price-based algorithm that divides menu items into thirds and selects one item from each price tier
- **Time-Based Filtering**: Automatically filters lunch items based on current time (Mon-Fri 11:00 AM - 3:00 PM ET)
- **Category Filtering**: Filter recommendations by menu categories (Appetizers, Seafood, Beef, Pork, etc.)
- **Price Range Filtering**: Set minimum and maximum price limits for recommendations

## API Endpoints

### GET /
Returns basic API information and status.

### GET /health
Health check endpoint for monitoring.

### POST /recommend
Get personalized menu recommendations.

**Request Body:**
```json
{
  "args": {
    "category": "Appetizers",
    "price_range": {
      "min": 5.0,
      "max": 15.0
    }
  }
}
```

**Response:**
```json
{
  "items": [
    {
      "name": "Egg Roll (2)",
      "price": 3.50,
      "category": "Appetizers",
      "is_lunch_item": false
    },
    {
      "name": "Spicy Wonton",
      "price": 9.95,
      "category": "Appetizers", 
      "is_lunch_item": false
    },
    {
      "name": "Beef & Beef Tendon with Szchuan Sauce",
      "price": 12.95,
      "category": "Appetizers",
      "is_lunch_item": false
    }
  ]
}
```

## Local Development

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Run the application:
   ```bash
   uvicorn recommend:app --reload --host 0.0.0.0 --port 8000
   ```

3. Visit `http://localhost:8000/docs` for interactive API documentation.

## Deployment to Fly.io

1. Install Fly CLI and login:
   ```bash
   fly auth login
   ```

2. Deploy the application:
   ```bash
   fly deploy
   ```

3. Your API will be available at: `https://your-app-name.fly.dev`

## Example Usage

```bash
# Get recommendations for appetizers under $15
curl -X POST "https://your-app-name.fly.dev/recommend" \
  -H "Content-Type: application/json" \
  -d '{
    "args": {
      "category": "Appetizers",
      "price_range": {"min": 0, "max": 15}
    }
  }'

# Get all recommendations in price range
curl -X POST "https://your-app-name.fly.dev/recommend" \
  -H "Content-Type: application/json" \
  -d '{
    "args": {
      "price_range": {"min": 10, "max": 20}
    }
  }'
```

## Menu Categories

- Appetizers
- Soup  
- Egg Foo Young
- Seafood Combination
- Beef
- Pork
- Vegetarian's Choice
- Poultry
- Lo Mein, Fried Rice, Noodle & Chow Mein
- Lunch Special
- Drink 