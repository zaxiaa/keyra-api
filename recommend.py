import re
import json
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime
import pytz
import random

# --- 1. SETUP FASTAPI APP ---
app = FastAPI(title="Restaurant Recommendation API", version="1.0.0")

# --- 2. PYDANTIC MODELS ---
class PriceRange(BaseModel):
    min: float
    max: float

class RecommendationRequest(BaseModel):
    args: Dict[str, Any]

class MenuItem(BaseModel):
    name: str
    price: float
    category: str
    is_lunch_item: bool

class RecommendationResponse(BaseModel):
    items: List[MenuItem]

# --- 3. MENU PARSING LOGIC (MODIFIED TO INCLUDE CATEGORIES & LUNCH FLAG) ---
def parse_menu(text: str) -> list[dict]:
    """
    Parses the menu text, now assigning a category and a lunch flag to each item.
    """
    menu_items = []
    current_category = "Unknown"
    price_regex = re.compile(r'\$(\d+\.\d+)')
    lines = text.splitlines()

    for line in lines:
        line = line.strip()
        
        # Detect category headers like "## Appetizers"
        category_match = re.match(r'^##\s*(.*)', line)
        if category_match:
            current_category = category_match.group(1).strip()
            continue

        if not line or '|--' in line or '| Code |' in line or line.startswith('**Mon'):
            continue
        
        # This parsing logic now adds 'category' and 'is_lunch_item' keys
        simple_item_match = re.match(r'-\s*\*\*.*\*\*\s*(.*?)\s*-\s*\$(.*)', line)
        if simple_item_match:
            name = simple_item_match.group(1).strip()
            price_str = simple_item_match.group(2).strip()
            price_match = re.match(r'(\d+\.\d+)', price_str)
            if price_match:
                menu_items.append({"name": name, "price": float(price_match.group(1)), "category": current_category, "is_lunch_item": False})
            continue
        
        drink_match = re.match(r'([A-Za-z\s]+?)\s*-\$([\d\.]+)', line)
        if drink_match:
            name = drink_match.group(1).strip()
            price_str = drink_match.group(2).strip()
            price_match = re.match(r'(\d+\.\d+)', price_str)
            if price_match:
                menu_items.append({"name": name, "price": float(price_match.group(1)), "category": "Drink", "is_lunch_item": False})
            continue

        if line.startswith('|'):
            parts = [p.strip() for p in line.split('|') if p.strip()]
            if len(parts) < 2: continue
            name_part = parts[1]
            if name_part in ["Item", "Item ", " Chinese Name "]: continue
            prices = price_regex.findall(line)

            # Handle tables with Lunch and Dinner prices
            if len(prices) == 2:
                # Add Lunch item with a flag
                menu_items.append({"name": f"{name_part} (Lunch)", "price": float(prices[0]), "category": current_category, "is_lunch_item": True})
                # Add Dinner item
                menu_items.append({"name": f"{name_part} (Dinner)", "price": float(prices[1]), "category": current_category, "is_lunch_item": False})
            
            # Handle tables with a single price (Dinner, Lunch Special, etc.)
            elif len(prices) == 1:
                is_lunch = True if current_category == "Lunch Special" else False
                price = float(prices[0])
                if "/" in name_part:
                    choices = name_part.split('/')
                    menu_items.append({"name": f"{choices[0].strip()}", "price": price, "category": current_category, "is_lunch_item": is_lunch})
                    menu_items.append({"name": f"{choices[1].strip()}", "price": price, "category": current_category, "is_lunch_item": is_lunch})
                else:
                    menu_items.append({"name": name_part, "price": price, "category": current_category, "is_lunch_item": is_lunch})
    return menu_items

# --- 4. NEW RECOMMENDATION LOGIC ---
def get_recommendations_from_list_thirds(items: list[dict]) -> dict:
    """
    Takes a list of items, sorts it by price, divides the list into thirds,
    and randomly selects one item from each third.
    """
    if not items:
        return {"items": []}

    # 1. Sort the list of items by price
    sorted_items = sorted(items, key=lambda x: x['price'])
    n = len(sorted_items)
    
    # Handle cases with very few items by returning a random sample
    if n < 3:
        return {"items": random.sample(sorted_items, k=n)}

    # 2. Divide the sorted LIST into three groups by index
    third_size = n // 3
    first_third_list = sorted_items[0:third_size]
    second_third_list = sorted_items[third_size : 2 * third_size]
    third_third_list = sorted_items[2 * third_size:]

    recommendations = []

    # 3. Randomly select one item from each non-empty list group
    if first_third_list:
        recommendations.append(random.choice(first_third_list))
    if second_third_list:
        recommendations.append(random.choice(second_third_list))
    if third_third_list:
        recommendations.append(random.choice(third_third_list))
        
    return {"items": recommendations}

# --- 5. PRE-LOAD THE MENU DATA ---
menu_text = """
# Hong Kong Palace Menu
## Appetizers

- **A1.** Egg Roll (2) - $3.50  
- **A2.** Vegetable Spring Roll (2) - $3.50  
- **A3.** Green Onion Pancake - $8.95  
- **A4.** Sesame Ball (6) - $9.95  
- **A5.** Shrimp Tempura (4) - $9.95  
- **A6.** Chengdu Zhongs Spring Dumpling - $9.95  (spicy & numb)
- **A7.** Spicy Wonton - $9.95  (spicy & numb)
- **A9.** Fried Chicken Wings (6) - $9.95  
- **A10.** Fried Wonton (8) - $9.95  
- **A11.** Vegetable or Meat Dumpling (Steamed or Fried) - $9.95  
- **A13.** Crab Meat Fried Wonton (8) - $9.95  
- **A14.** Bar-B-Q Spareribs (4) - $9.95  
- **A15.** Beef & Beef Tendon with Szchuan Sauce - $12.95  (spicy & numb)
- **A16.** Sliced Pork with Garlic Sauce - $12.95  
- **A17.** Delightful Cold Wooden Ear Mushroom Salad - $10.95  
- **A18.** Chengdu Spicy Cold Noodle - $10.95  (spicy & numb)
- **A19.** Five Spicy Pressed Bean Curd - $10.95  
- **A20.** Dan Dan Noodle - $10.95  (spicy & numb)
- **A21.** Mini Wonton Chicken Broth - $10.95  
- **A22.** Spicy Szechuan Dry Beef - $12.95  (spicy & numb)
- **A23.** Fried Dry Fish with Peanut - $12.95  

## Soup

| Code | Item                                | Small  | Large  |
|------|-------------------------------------|--------|--------|
| SU1  | Egg Drop Soup                       | $2.95  | $5.95  |
| SU2  | Wonton Soup                         | $3.95  | $6.95  |
| SU3  | Hot & Sour Soup                     | $2.95  | $5.95  | (spicy)
| SU4  | Chicken Corn Soup                   |        | $11.95 |
| SU5  | Vegetable Tofu Soup                 |        | $11.95 |
| SU6  | Chicken with Pickled Vegetable Soup |        | $11.95 |
| SU7  | Sea Food Soup                       |        | $12.95 |
| SU8  | Sea Food Bean Curd Soup             |        | $12.95 |
| SU9  | Triple Delight Soup                 |        | $12.95 |
| SU10 | Hot & Sour Sea Food Soup            |        | $12.95 | (spicy)
| SU11 | Fish with Pickled Vegetable Soup    |        | $12.95 |
| SU12 | West Lake Beef Soup                 |        | $12.95 |

## Egg Foo Young

| Code | Item                      | Price  |
|------|---------------------------|--------|
| E1   | Beef Egg Foo Young        | $16.95 |
| E2   | Shrimp Egg Foo Young      | $16.95 |
| E3   | Combination Egg Foo Young| $16.95 |
| E4   | Chicken Egg Foo Young     | $15.95 |
| E5   | Pork Egg Foo Young        | $15.95 |
| E6   | Vegetable Egg Foo Young   | $15.95 |

## Seafood Combination

| Code | Item                                      | Lunch  | Dinner  |
|------|-------------------------------------------|--------|---------|
| S1   | Hunan Shrimp                              | $11.95 | $16.95  | (spicy)
| S2   | Shrimp with Broccoli                      | $11.95 | $16.95  |
| S3   | Shrimp with Black Bean Sauce              | $11.95 | $16.95  |
| S4   | Shrimp with Vegetable                     | $11.95 | $16.95  |
| S5   | Szechuan Shrimp                           | $11.95 | $16.95  | (spicy)
| S6   | Kung Pao Shrimp                           | $11.95 | $16.95  | (spicy)
| S7   | Sweet & Sour Shrimp                       | $11.95 | $16.95  |
| S8   | Shrimp with Lobster Sauce                 | $11.95 | $16.95  |
| S9   | Fish & Bean Curd with Spicy Sauce         |        | $19.95  | (spicy & numb)
| S10  | Fresh Fish Filet                          |        | $19.95  |
| S11  | Sweet & Sour Fish Filet                   |        | $19.95  |
| S12  | Garlic Flavor Fried Flounders             |        | $19.95  |
| S14  | Steamed Whole Fish w. Ginger & Green Onion|        | $36.95  |
| S15  | Whole Fish with Spicy Bean Sauce          |        | $36.95  |
| S16  | Braised Fish with Bean Curd               |        | $38.95  | (spicy & numb)
| S17  | Special Hotpot Sauce with Fresh Fish      |        | $40.95  | (spicy & numb)
| S20  | Jade Jumbo Shrimp                         |        | $19.95  | 
| S21  | Chengdu Salt & Pepper Jumbo Shrimp        |        | $19.95  |
| S24  | Fresh Squid w. Black Bean Sauce           |        | $18.95  |
| S25  | Stir Fried Squid with Pickled Pepper      |        | $18.95  | (spicy)
| S26  | Scallops with Hot Garlic Sauce            |        | $18.95  | (spicy)
| S27  | Scallops with Vegetables                                   |        | $18.95  | 
| S28  | Scallops & Shrimp in Hot Garlic Sauce                      |        | $18.95  | (spicy)
| S29  | Seafood Combination                                        |        | $18.95  |
| S30  | Cumin Fish                                                 |        | $19.95  | (spicy & numb)
| S31  | Triple Delight (Shrimp, beef, chicken & vegetables)        |        | $18.95  |
| S32  | Kung Pao Chicken and Shrimp                                |        | $18.95  | (spicy)
| S33  | Beef and Scallops                                          |        | $18.95  |
| S34  | Family Delight                                             |        | $18.95  |
| S35  | Kung Pao Triple Delight                                    |        | $18.95  | (spicy)
| S36  | Fish or Beef or Chicken with Vegetable in Peppery Broth    |        | $19.95  | (spicy & numb)

## Beef

| Code | Item                                           | Lunch  | Dinner  |
|------|------------------------------------------------|--------|---------|
| B1   | Hunan Beef                                     | $11.95 | $16.95  |
| B2   | Beef with Snow Peas                            | $11.95 | $16.95  |
| B3   | Beef with Spring Onion                         | $11.95 | $16.95  |
| B4   | Beef with Broccoli                             | $11.95 | $16.95  |
| B5   | Beef with Green Pepper                         | $11.95 | $16.95  |
| B6   | Beef with Mixed Vegetables                     | $11.95 | $16.95  |
| B7   | Szechuan Beef                                  | $11.95 | $16.95  |
| B8   | Beef with String Bean                          | $11.95 | $16.95  |
| B9   | Kung Pao Beef                                  |        | $16.95  |
| B10  | Shredded Beef with Chinese Celery              |        | $16.95  |
| B11  | Shredded Beef with Pickled Vegetable           |        | $17.95  |
| B12  | Shredded Beef w. Fresh Baby Bamboo Shoots      |        | $17.95  |
| B13  | Orange Beef                                    |        | $18.95  |
| B14  | Sesame Beef                                    |        | $18.95  |
| B15  | Crispy Beef (Szechuan Style)                   |        | $18.95  |
| B16  | Braised Beef Tenderloin with Bamboo Shoots     |        | $18.95  |
| B17  | Braised Beef Tenderloin with Beer Sauce        |        | $18.95  |
| B18  | Cumin Beef/Lamb                                |        | $19.95  |

## Pork

| Code | Item                                                 | Lunch  | Dinner  |
|------|------------------------------------------------------|--------|---------|
| P1   | Hunan Pork                                           | $10.95 | $15.95  |
| P2   | Moo Shu Pork                                         | $10.95 | $15.95  |
| P3   | Pork with Hot Garlic Sauce                           | $10.95 | $15.95  |
| P4   | Pork with Spring Onion                               | $10.95 | $15.95  |
| P5   | Ground Pork with Vermicelli                          |        | $16.95  |
| P6   | Twice Cooked Pork with Dry Long Bean                 |        | $17.95  |
| P7   | Stir Fried Shredded Pork w. Green Hot Pepper         |        | $16.95  |
| P8   | Twice Cooked Pork with Fresh Garlic Leaves           |        | $17.95  |
| P9   | Stir Fried Ground Pork with Pickled Long Bean        |        | $16.95  |
| P10  | Stir Fried Pork with Wooden Ear Mushroom             |        | $16.95  |
| P11  | Shredded Pork with Chinese Celery                    |        | $16.95  |
| P12  | Shredded Pork with Pickled Vegetable                 |        | $16.95  |
| P13  | Shredded Pork with Dry Bean Curd                     |        | $16.95  |
| P14  | Salt & Pepper Pork Chop                              |        | $18.95  |
| P15  | Dong Po Braised Pork                                 |        | $16.95  |
| P16  | Old Buddhist Braised Pork                            |        | $16.95  |
| P17  | Spicy Sichaun Ribs                                   |        | $16.95  |
| P18  | Cumin Ribs                                           |        | $16.95  |

## Vegetarian's Choice

| Code | Item                                                | Lunch  | Dinner   |
|------|-----------------------------------------------------|--------|----------|
| V1   | Stir Fried Vegetables                               | $9.95  | $14.95   |
| V2   | Bean Curd Vegetables                                | $9.95  | $14.95   |
| V3   | Moo Shu Vegetables                                  | $9.95  | $14.95   |
| V4   | Ma Po Tofu                                          |        | $15.95   |
| V5   | Home Style Bean Curd *(Chinese style add meat)*     | $9.95  | $16.95   |
| V6   | Stir Fried Potato & Green Pepper                    |        | $14.95   |
| V7   | Eggplant with Hot Garlic Sauce                      |        | $14.95   |
| V9   | Pan Fried Eggs with Bitter Melon                    |        | $14.95   |
| V10  | Stir Fried Bitter Melon                             |        | $14.95   |
| V11  | Stir Fried String Bean                              |        | $14.95   |
| V12  | Pan Fried Celery & Wooden Ear Mushroom              |        | $14.95   |
| V13  | Stir Fried Dry Bean Curd w. Chinese Celery          |        | $14.95   |
| V14  | Tiger Skin Pepper                                   |        | $15.95   | (spicy)
| V16  | Stir Fried Shanghai Green & Black Mushroom          |        | $14.95   |
| V17  | Fried Spinach with Fresh Garlic                     |        | $14.95   |
| V18  | Kung Pao Tofu                                       |        | $14.95   | (spicy)


## Poultry

| Code | Item                                           | Lunch  | Dinner  |
|------|------------------------------------------------|--------|---------|
| C1   | Hunan Chicken                                  | $10.95 | $15.95  | (spicy)
| C2   | Chicken with String Beans                      | $10.95 | $15.95  |
| C3   | Chicken with Eggplant                          | $10.95 | $15.95  |
| C4   | Chicken with Hot Garlic Sauce                  | $10.95 | $15.95  | (spicy)
| C5   | Chengdu Kung Pao Chicken                       |        | $15.95  | (spicy & numb)
| C6   | Chicken with Broccoli                          | $10.95 | $15.95  |
| C7   | Chicken with Mixed Vegetables                  | $10.95 | $15.95  | (alias: Steamed Chicken with Vegetables and Brown Sauce)
| C8   | Chicken with Snow Peas                         | $10.95 | $15.95  |
| C9   | Chicken with Cashew Nuts                       | $10.95 | $15.95  |
| C10  | Sweet & Sour Chicken                           | $10.95 | $15.95  |
| C11  | Moo Goo Gai Pan                                | $10.95 | $15.95  |
| C12  | Chicken with Black Bean Sauce                  | $10.95 | $15.95  |
| C13  | Moo Shu Chicken                                | $10.95 | $15.95  |
| C14  | Curry Chicken                                  | $10.95 | $15.95  | (spicy)
| C15  | Szechuan Chicken                               | $10.95 | $15.95  | (spicy)
| C16  | Shredded Chicken with Pickled Vegetable        |        | $16.95  |
| C17  | Diced Chicken with Hot Peppers                 |        | $16.95  | (spicy & numb)
| C18  | Fried Chicken with Dry Chili Peppers           |        | $16.95  | (spicy & numb)
| C19  | Fried Chicken with Spicy Potato                |        | $16.95  | (spicy & numb)
| C21  | General Tso's Chicken                          |        | $16.95  | (spicy)
| C22  | Sesame Chicken                                 |        | $16.95  |
| C23  | Orange Chicken                                 |        | $16.95  | (spicy)
| C24  | Chengdu Tea-smoked Duck (Half)                 |        | $24.95  |

## Lo Mein, Fried Rice, Noodle & Chow Mein

| Code | Item                                          | Lunch  | Dinner  |
|------|-----------------------------------------------|--------|---------|
| RL1a | Fried Rice (Choice of Beef, Chicken, BBQ Pork, Vegetable, Shrimp) | $9.00  | $11.95  |
| RL1b | Lo Mein (Choice of Beef, Chicken, BBQ Pork, vegetable, Shrimp) | $9.00  | $11.95  |
| RL2 | Combination Lo Mein or Rice                   | $9.00  | $11.95  |
| R1   | Egg Fried Rice                                |        | $11.95  |
| R2   | Yang Zhou Fried Rice                          |        | $13.95  |
| N1   | Braised Beef Noodle Soup                      |        | $13.95  | (spicy)
| N2   | Shredded Chicken Pickled Mustard Noodle Soup  |        | $12.95  |
| N3   | Pork with Pickled Vegetable Noodle Soup       |        | $12.95  |
| N4   | Triple-Delight Noodle Soup                    |        | $13.95  |
| N5   | Noodle with Brown Meat Sauce                  |        | $12.95  | (spicy)
| N6   | Singapore Style Rice Noodles                  |        | $14.95  | (spicy)
| N7   | Beef Chow Fun                                 |        | $16.95  |

## Lunch Special  
**Mon – Fri: 11:00 am – 3:00 pm**  
*Served with white rice*

| #   | Item                              | Price   |
|-----|-----------------------------------|---------|
| 2   | Sweet & Sour Pork/Chicken         | $9.95   |
| 3   | Hunan Pork/Chicken                | $9.95   | (spicy)
| 4   | Chicken with Cashew Nuts          | $9.95   |
| 5   | Moo Goo Gai Pan                   | $9.95   |
| 6   | Vegetable Delight                 | $9.95   |
| 7   | Cumin Chicken                     | $9.95   | (spicy)
| 8   | Kung Pao Chicken                  | $9.95   | (spicy)
| 9   | Szechuan Chicken                  | $9.95   | (spicy)
| 10  | Chicken with Broccoli             | $9.95   |
| 11  | Chicken with Mixed Vegetables     | $9.95   |
| 12  | Shrimp with Mixed Vegetables      | $10.95  |
| 13  | Beef with Mixed Vegetables        | $10.95  |
| 14  | Crispy Chicken/Beef               | $10.95  | (spicy)
| 15  | Sesame Chicken                    | $10.95  |
| 16  | Orange Chicken                    | $10.95  | (spicy)
| 17  | General Tso's Chicken             | $10.95  | (spicy)
| 19  | Pepper Steak                      | $10.95  |
| 20  | Beef with Broccoli                | $10.95  |
| 21  | Szechuan Beef                     | $10.95  |


## Drink
Coke          - $2.00
Diet Coke   -$2.00
Ginger Ale  -$2.00
Sprite          -$2.00
Bottled Water -$1.5
"""
FULL_MENU = parse_menu(menu_text)

# --- 6. API ENDPOINTS ---
@app.get("/")
async def root():
    return {"message": "Restaurant Recommendation API", "status": "running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.post("/recommend", response_model=RecommendationResponse)
async def recommend(request_data: RecommendationRequest):
    # Time-based filtering is always active
    tz = pytz.timezone('US/Eastern')
    now = datetime.now(tz)
    is_lunch_hours = (0 <= now.weekday() <= 4) and (11 <= now.hour < 15)
    
    if is_lunch_hours:
        time_filtered_menu = FULL_MENU
    else:
        time_filtered_menu = [item for item in FULL_MENU if not item.get("is_lunch_item", False)]

    # Extract arguments from request
    args = request_data.args
    category = args.get('category')
    price_range = args.get('price_range')

    # Filter by category first, if provided
    if category:
        candidate_items = [item for item in time_filtered_menu if category.lower() in item['category'].lower()]
    else:
        candidate_items = time_filtered_menu
    
    try:
        min_price = float(price_range['min'])
        max_price = float(price_range['max'])
        candidate_items = [item for item in candidate_items if min_price <= item.get("price", 0) <= max_price]
    except (KeyError, TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid price_range format.")

    # Pass the final list of candidates to the recommendation logic
    return get_recommendations_from_list_thirds(candidate_items)

# --- 7. FOR DEPLOYMENT ---
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)