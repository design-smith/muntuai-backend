from fastapi import APIRouter, Depends, HTTPException, Body, Request
from backend.routers.auth_utils import get_current_user
from backend.data_services.stripe_service import (
    get_or_create_stripe_customer, attach_payment_method_to_customer, create_subscription, cancel_subscription, sync_subscription_to_db,
    list_payment_methods, detach_payment_method, list_invoices, verify_stripe_webhook,
    update_subscription_status_by_stripe_customer, set_default_payment_method
)
from backend.data_services.mongo.mongo_client import get_database
import logging

router = APIRouter()
db = get_database()

@router.get("/billing/plan")
def get_current_plan(user=Depends(get_current_user)):
    # Return the user's current plan/subscription info
    u = db.users.find_one({"_id": user["_id"]})
    return {"plan": u.get("subscription", {})}

@router.post("/billing/payment-method")
def add_payment_method(payment_method_id: str = Body(...), user=Depends(get_current_user)):
    # Attach payment method to Stripe customer
    u = db.users.find_one({"_id": user["_id"]})
    customer = get_or_create_stripe_customer(u)
    attach_payment_method_to_customer(customer.id, payment_method_id)
    return {"status": "success"}

@router.get("/billing/payment-methods")
def get_payment_methods(user=Depends(get_current_user)):
    u = db.users.find_one({"_id": user["_id"]})
    customer = get_or_create_stripe_customer(u)
    methods = list_payment_methods(customer.id)
    return {"payment_methods": methods.data}

@router.delete("/billing/payment-method/{payment_method_id}")
def remove_payment_method(payment_method_id: str, user=Depends(get_current_user)):
    detach_payment_method(payment_method_id)
    return {"status": "removed"}

@router.post("/billing/subscribe")
def subscribe_to_plan(price_id: str = Body(...), user=Depends(get_current_user)):
    # Create a Stripe subscription for the user
    u = db.users.find_one({"_id": user["_id"]})
    customer = get_or_create_stripe_customer(u)
    subscription = create_subscription(customer.id, price_id)
    sync_subscription_to_db(u["_id"], subscription)
    return {"status": "subscribed", "subscription_id": subscription.id}

@router.post("/billing/cancel")
def cancel_user_subscription(user=Depends(get_current_user)):
    # Cancel the user's Stripe subscription
    u = db.users.find_one({"_id": user["_id"]})
    sub_id = u.get("subscription", {}).get("stripe_subscription_id")
    if not sub_id:
        raise HTTPException(status_code=400, detail="No active subscription")
    cancel_subscription(sub_id)
    db.users.update_one({"_id": u["_id"]}, {"$set": {"subscription.status": "canceled"}})
    return {"status": "canceled"}

@router.get("/billing/invoices")
def get_invoices(user=Depends(get_current_user)):
    u = db.users.find_one({"_id": user["_id"]})
    customer = get_or_create_stripe_customer(u)
    invoices = list_invoices(customer.id)
    return {"invoices": invoices.data}

@router.post("/billing/set-default-payment-method")
def set_default_pm(payment_method_id: str = Body(...), user=Depends(get_current_user)):
    u = db.users.find_one({"_id": user["_id"]})
    if not u or not u.get("subscription", {}).get("stripe_customer_id"):
        raise HTTPException(status_code=404, detail="User or Stripe customer not found")
    try:
        set_default_payment_method(u["subscription"]["stripe_customer_id"], payment_method_id)
        return {"status": "success"}
    except Exception as e:
        logging.error(f"Failed to set default payment method: {e}")
        raise HTTPException(status_code=500, detail="Failed to set default payment method")

@router.post("/billing/webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    event = verify_stripe_webhook(request, payload, sig_header)
    logging.info(f"Stripe webhook event received: {event['type']}")
    # Handle event types
    if event["type"] == "invoice.payment_succeeded":
        invoice = event["data"]["object"]
        customer_id = invoice["customer"]
        subscription_id = invoice.get("subscription")
        current_period_start = invoice.get("lines", {}).get("data", [{}])[0].get("period", {}).get("start")
        current_period_end = invoice.get("lines", {}).get("data", [{}])[0].get("period", {}).get("end")
        update_subscription_status_by_stripe_customer(
            customer_id, "active", subscription_id, current_period_start, current_period_end
        )
        logging.info(f"Updated subscription status to active for customer {customer_id}")
    elif event["type"] in ["customer.subscription.deleted", "customer.subscription.canceled"]:
        subscription = event["data"]["object"]
        customer_id = subscription["customer"]
        update_subscription_status_by_stripe_customer(customer_id, "canceled")
        logging.info(f"Marked subscription as canceled for customer {customer_id}")
    elif event["type"] in ["customer.subscription.created", "customer.subscription.updated"]:
        subscription = event["data"]["object"]
        customer_id = subscription["customer"]
        subscription_id = subscription["id"]
        status = subscription["status"]
        current_period_start = subscription.get("current_period_start")
        current_period_end = subscription.get("current_period_end")
        update_subscription_status_by_stripe_customer(
            customer_id, status, subscription_id, current_period_start, current_period_end
        )
        logging.info(f"Updated subscription status to {status} for customer {customer_id}")
    # ... handle other event types as needed
    return {"status": "success"} 