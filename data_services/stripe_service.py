import os
import stripe
from backend.data_services.mongo.mongo_client import get_database
from datetime import datetime
from fastapi import HTTPException, Request

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")

db = get_database()

# --- Stripe Customer Management ---
def get_or_create_stripe_customer(user):
    """
    Ensure a Stripe customer exists for the user. Returns the Stripe customer object.
    """
    stripe_customer_id = user.get("subscription", {}).get("stripe_customer_id")
    if stripe_customer_id:
        try:
            return stripe.Customer.retrieve(stripe_customer_id)
        except Exception as e:
            print(f"Stripe customer retrieve error: {e}")
    try:
        customer = stripe.Customer.create(
            email=user["email"],
            name=user.get("name", ""),
            metadata={"user_id": str(user["_id"])}
        )
        db.users.update_one({"_id": user["_id"]}, {"$set": {"subscription.stripe_customer_id": customer.id}})
        return customer
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Stripe customer creation failed: {e}")

# --- Payment Method Management ---
def attach_payment_method_to_customer(stripe_customer_id, payment_method_id):
    """
    Attach a payment method to a Stripe customer and set as default.
    """
    try:
        stripe.PaymentMethod.attach(payment_method_id, customer=stripe_customer_id)
        stripe.Customer.modify(stripe_customer_id, invoice_settings={"default_payment_method": payment_method_id})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Attach payment method failed: {e}")

def list_payment_methods(stripe_customer_id):
    try:
        return stripe.PaymentMethod.list(customer=stripe_customer_id, type="card")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"List payment methods failed: {e}")

def detach_payment_method(payment_method_id):
    try:
        return stripe.PaymentMethod.detach(payment_method_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Detach payment method failed: {e}")

# --- Subscription Management ---
def create_subscription(stripe_customer_id, price_id):
    """
    Create a Stripe subscription for the customer with the given price ID.
    """
    try:
        subscription = stripe.Subscription.create(
            customer=stripe_customer_id,
            items=[{"price": price_id}],
            expand=["latest_invoice.payment_intent"]
        )
        return subscription
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Create subscription failed: {e}")

def cancel_subscription(stripe_subscription_id):
    """
    Cancel a Stripe subscription.
    """
    try:
        return stripe.Subscription.delete(stripe_subscription_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cancel subscription failed: {e}")

# --- Utility: Sync Stripe data to MongoDB ---
def sync_subscription_to_db(user_id, subscription):
    db.users.update_one(
        {"_id": user_id},
        {"$set": {
            "subscription.stripe_subscription_id": subscription.id,
            "subscription.status": subscription.status,
            "subscription.current_period_start": datetime.fromtimestamp(subscription.current_period_start),
            "subscription.current_period_end": datetime.fromtimestamp(subscription.current_period_end)
        }}
    )

# --- Invoices ---
def list_invoices(stripe_customer_id):
    try:
        return stripe.Invoice.list(customer=stripe_customer_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"List invoices failed: {e}")

# --- Webhook Verification ---
def verify_stripe_webhook(request: Request, payload: bytes, sig_header: str):
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
        return event
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Webhook signature verification failed: {e}")

def update_subscription_status_by_stripe_customer(stripe_customer_id, status, subscription_id=None, current_period_start=None, current_period_end=None):
    user = db.users.find_one({"subscription.stripe_customer_id": stripe_customer_id})
    if not user:
        return False
    update = {"subscription.status": status}
    if subscription_id:
        update["subscription.stripe_subscription_id"] = subscription_id
    if current_period_start:
        update["subscription.current_period_start"] = datetime.fromtimestamp(current_period_start)
    if current_period_end:
        update["subscription.current_period_end"] = datetime.fromtimestamp(current_period_end)
    db.users.update_one({"_id": user["_id"]}, {"$set": update})
    return True

def set_default_payment_method(stripe_customer_id, payment_method_id):
    try:
        stripe.Customer.modify(stripe_customer_id, invoice_settings={"default_payment_method": payment_method_id})
        # Optionally update in MongoDB if you store default locally
        user = db.users.find_one({"subscription.stripe_customer_id": stripe_customer_id})
        if user:
            db.users.update_one({"_id": user["_id"]}, {"$set": {"subscription.default_payment_method_id": payment_method_id}})
        return True
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Set default payment method failed: {e}") 