# Use an official Python runtime as a parent image
FROM python:3.9

# Set the working directory in the container
WORKDIR /app

# Copy the frontend.py file into the container at /app
COPY frontend.py .

# Copy the templates directory into the container at /app/templates
COPY /templates ./templates

COPY config.ini .

# Install any needed packages specified in requirements.txt
# If you have any, uncomment the next line and include your requirements.txt file
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Make port 80 available to the world outside this container
EXPOSE 80

# Define environment variable
# ENV NAME World

# Run frontend.py when the container launches
CMD ["python", "frontend.py"]
