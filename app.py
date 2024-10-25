from flask import Flask, render_template, request, redirect, url_for, session
import boto3
import os
import json  # Import the json module

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Secret key for session management

# Initialize AWS DynamoDB and S3 clients
dynamodb = boto3.resource('dynamodb')
s3 = boto3.client('s3')

# DynamoDB Tables
furniture_table = dynamodb.Table('Furniture')  # Table for furniture details
customer_info_table = dynamodb.Table('CustomerInfo')  # Table for storing customer info

# S3 bucket name for storing furniture images
S3_BUCKET_NAME = 'furnitureimage91'

# Function to get all furniture items from DynamoDB
def get_all_furniture():
    response = furniture_table.scan()
    return response['Items']

# Function to get furniture items by category from DynamoDB
def get_furniture_by_category(category):
    response = furniture_table.scan(FilterExpression='category = :cat', ExpressionAttributeValues={':cat': category})
    return response['Items']

# Function to get a furniture item by item_id
def get_furniture_by_id(item_id):
    response = furniture_table.get_item(Key={'item_id': item_id})
    return response.get('Item', {})

# Function to upload a furniture image to S3
def upload_image_to_s3(image, item_id):
    file_name = f"{item_id}.jpg"  # Assume the image is a jpg
    s3.upload_fileobj(image, S3_BUCKET_NAME, file_name)
    return f"https://{S3_BUCKET_NAME}.s3.amazonaws.com/{file_name}"

# Home route - Display all furniture items
@app.route('/')
def home():
    items = get_all_furniture()
    return render_template('index.html', items=items)

# Route for products selection
@app.route('/products')
def products():
    return render_template('products.html')

# Route for category products
@app.route('/products/<category>')
def category_products(category):
    items = get_furniture_by_category(category)
    if not items:
        return f"No products found in the {category} category.", 404
    return render_template('category_products.html', items=items, category=category)

# Route for viewing furniture details
@app.route('/furniture/<item_id>')
def furniture_detail(item_id):
    item = get_furniture_by_id(item_id)
    if not item:
        return "Furniture item not found", 404
    return render_template('furniture_detail.html', item=item)
@app.route('/add_to_cart/<item_id>')
def add_to_cart(item_id):
    # Initialize the cart if it doesn't exist
    if 'cart' not in session:
        session['cart'] = {}

    # Check if the item is already in the cart
    if item_id in session['cart']:
        session['cart'][item_id] += 1  # Increment quantity
    else:
        session['cart'][item_id] = 1  # Set quantity to 1

    session.modified = True  # Mark session as modified to save changes
    return redirect(url_for('cart'))


@app.route('/cart')
def cart():
    cart_items = []
    total_price = 0

    # Check if 'cart' exists in the session
    if 'cart' in session:
        for item_id, quantity in session['cart'].items():
            item = get_furniture_by_id(item_id)  # Fetch item details from DB
            if item:  # Ensure item is found before proceeding
                item['quantity'] = quantity  # Add quantity to item details
                cart_items.append(item)  # Append item with quantity to cart_items
                total_price += float(item['price']) * quantity  # Calculate total price

    return render_template('cart.html', cart_items=cart_items, total_price=total_price)

# Route for buying furniture
@app.route('/buy_now', methods=['GET', 'POST'])
def buy_now():
    if request.method == 'POST':
        # Store customer information in DynamoDB
        customer_info_table.put_item(
            Item={
                'name': request.form['name'],
                'email': request.form['email'],
                'phone_no': request.form['phone_no'],
                'address': request.form['address'],
                'payment_method': request.form['payment_method'],
                'cart_items': session.get('cart', [])
            }
        )
        session.pop('cart', None)  # Clear the cart after purchase
        
        # Trigger AWS Lambda to send email using SES
        send_purchase_confirmation(request.form['email'])

        return render_template('purchase_success.html')

    return render_template('buy_now.html')

# Function to trigger AWS Lambda for sending confirmation email
def send_purchase_confirmation(email):
    lambda_client = boto3.client('lambda')
    
    # Construct the payload for Lambda
    payload = {
        "email": email,
        "subject": "Purchase Confirmation",
        "message": "Thank you for your purchase! Your order has been successfully placed."
    }
    
    # Invoke the Lambda function
    response = lambda_client.invoke(
        FunctionName='success',  # Replace with your Lambda function name
        InvocationType='RequestResponse',
        Payload=json.dumps(payload)  # Use json.dumps to convert the payload to a JSON string
    )


if __name__ == '__main__':
    app.run(debug=True)
