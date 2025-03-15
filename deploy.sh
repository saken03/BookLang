#!/bin/bash

# BookLand Deployment Script
# This script helps automate the deployment process

# Exit on error
set -e

# Load environment variables
if [ -f .env ]; then
    echo "Loading environment variables from .env"
    export $(grep -v '^#' .env | xargs)
else
    echo "No .env file found. Please create one based on .env.example"
    exit 1
fi

# Check if DJANGO_SETTINGS_MODULE is set to production
if [ "$DJANGO_SETTINGS_MODULE" != "bookland.settings_prod" ]; then
    echo "Warning: DJANGO_SETTINGS_MODULE is not set to production settings"
    read -p "Do you want to continue? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Function to run a command with a header
run_step() {
    echo "============================================"
    echo ">>> $1"
    echo "============================================"
    eval "$2"
    echo
}

# Check for required commands
for cmd in python pip git; do
    if ! command -v $cmd &> /dev/null; then
        echo "Error: $cmd is required but not installed."
        exit 1
    fi
done

# Main deployment steps
run_step "Updating code from repository" "git pull"
run_step "Installing/updating dependencies" "pip install -r requirements.txt"
run_step "Running database migrations" "python manage.py migrate"
run_step "Collecting static files" "python manage.py collectstatic --noinput"

# Check if we need to restart services
read -p "Do you want to restart the Gunicorn service? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    if command -v systemctl &> /dev/null; then
        run_step "Restarting Gunicorn" "sudo systemctl restart bookland"
    else
        echo "Cannot restart Gunicorn: systemctl not found"
    fi
fi

read -p "Do you want to restart Nginx? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    if command -v systemctl &> /dev/null; then
        run_step "Restarting Nginx" "sudo systemctl restart nginx"
    else
        echo "Cannot restart Nginx: systemctl not found"
    fi
fi

# Final message
echo "============================================"
echo "Deployment completed successfully!"
echo "Don't forget to check the application is running correctly."
echo "============================================" 