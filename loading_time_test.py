from selenium import webdriver
from selenium.webdriver.firefox.options import Options
import time
import csv
import argparse

"""
Prerequisites:
- Install Firefox and geckodriver
- Install Selenium: pip install selenium
- Start a local web server serving the test page

This script tests the loading times of a specific image on a webpage using Selenium with Firefox.
It measures various timing metrics for the image loading process and saves the results to a CSV file.
It can be run multiple times to gather data for performance analysis.

- Waiting time is the time from when the request is sent until the first byte of the response is
  received.
- Receiving time is the time taken to receive the entire response after the first byte.
- Initiation time is the time taken from the start of the page load until the request for the image is initiated. 
  it includes:
    - DNS lookup (irrelevant for localhost)
    - TCP connection establishment (irrelevant for localhost)
    - TLS negotiation for HTTPS (irrelevant for localhost)
    - Request queuing/prioritization (relevant for localhost)
    - DOM interactions and JavaScript execution (relevant for localhost)
    
- Total time is the total time from the start of the page load until the image is fully loaded.

It also provides a summary of the results, including the number of valid iterations, total times,
and averages for each metric.
"""

# Parse command line arguments
parser = argparse.ArgumentParser(description='Test image loading times')
parser.add_argument('--url', default="http://127.0.0.1:8020/",
                    help='Target URL to test')
parser.add_argument('--target-image',
                    default="image.jpg",
                    help='Target image filename to monitor')
parser.add_argument('--iterations', type=int, default=100,
                    help='Number of iterations to run')
parser.add_argument('--output', default='image_load_times.csv',
                    help='Output CSV filename')

args = parser.parse_args()

# Use the parsed arguments
url = args.url
target_image = args.target_image
iterations = args.iterations
output_file = args.output

# Set up Firefox options with network monitoring and cache disabled
options = Options()
options.page_load_strategy = 'normal'

# Create a Firefox profile to disable cache
profile = webdriver.firefox.firefox_profile.FirefoxProfile()
profile.set_preference("browser.cache.disk.enable", False)
profile.set_preference("browser.cache.memory.enable", False)
profile.set_preference("browser.cache.offline.enable", False)
profile.set_preference("network.http.use-cache", False)

# Set the profile in the options
options.profile = profile

# Initialize the Firefox driver with these settings
driver = webdriver.Firefox(options=options)

# First run to get the exact image URL
print("Loading page to discover image URL...")
driver.get(url)
time.sleep(3)  # Wait for page to fully load

# Find our target image
resources = driver.execute_script("""
    return performance.getEntriesByType('resource')
        .filter(r => r.name.includes(arguments[0]))
        .map(r => {
            return {
                url: r.name,
                type: r.initiatorType,
                duration: r.duration
            };
        });
""", target_image)

if not resources:
    print(f"Target image not found! ({target_image})")
    driver.quit()
    exit(1)

# Use the first matching image URL as our target
target_image_url = resources[0]['url']
print(f"Found target image: {target_image_url}")

# Track summary data as we go
waiting_time_sum = 0
receiving_time_sum = 0
initiation_time_sum = 0
total_time_sum = 0
valid_iterations = 0
all_data = []  # Store all data for writing at the end

try:
    for i in range(iterations):
        print(f"Loading page: iteration {i + 1}/{iterations}")

        # Add cache-busting parameter to URL (each must be unique)
        modified_url = url + (f"?cachebust={i + 1}"
                              if '?' not in url else f"&cachebust={i + 1}")

        # Clear performance data
        driver.execute_script("performance.clearResourceTimings();")

        # Load the page
        driver.get(modified_url)
        time.sleep(2)  # Wait for page to load

        # Look for our image with the base URL
        timing = driver.execute_script("""
            var resources = performance.getEntriesByType('resource');
            for (var i = 0; i < resources.length; i++) {
                if (resources[i].name.includes(arguments[0])) {
                    return {
                        url: resources[i].name,
                        waitingTime: resources[i].responseStart - resources[i].requestStart,
                        receivingTime: resources[i].responseEnd - resources[i].responseStart,
                        initiationTime: resources[i].requestStart - resources[i].startTime,
                        totalTime: resources[i].responseEnd - resources[i].startTime
                    };
                }
            }
            return null;
        """, target_image)

        if timing:
            waiting_time = timing['waitingTime']
            receiving_time = timing['receivingTime']
            initiation_time = timing['initiationTime']
            total_time = timing['totalTime']

            # Add to running sums for summary
            waiting_time_sum += waiting_time
            receiving_time_sum += receiving_time
            initiation_time_sum += initiation_time
            total_time_sum += total_time
            valid_iterations += 1

            # Store data for writing to CSV
            all_data.append({
                'iteration': i + 1,
                'waiting_time_ms': waiting_time,
                'receiving_time_ms': receiving_time,
                'initiation_time_ms': initiation_time,
                'total_time_ms': total_time
            })

            print(
                f"  Waiting: {waiting_time:.2f}ms, Receiving: {receiving_time:.2f}ms, Initiation: {initiation_time:.2f}ms, Total: {total_time:.2f}ms")
        else:
            print(f"  Image not found in iteration {i + 1}")
            all_data.append({
                'iteration': i + 1,
                'waiting_time_ms': 'N/A',
                'receiving_time_ms': 'N/A',
                'initiation_time_ms': 'N/A',
                'total_time_ms': 'N/A'
            })
finally:
    # Write all data to CSV at once
    try:
        with open(output_file, 'w', newline='') as csvfile:
            fieldnames = ['iteration', 'waiting_time_ms', 'receiving_time_ms', 'initiation_time_ms', 'total_time_ms']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            # Write all iteration data
            for row in all_data:
                writer.writerow(row)

            # Add empty row for separation
            writer.writerow({field: '' for field in fieldnames})

            # Write summary rows using a different approach
            summary_data = [
                {field: 'SUMMARY' if field == 'iteration' else '' for field in fieldnames},
                {'iteration': 'Valid iterations', 'waiting_time_ms': valid_iterations,
                 'receiving_time_ms': '', 'initiation_time_ms': '', 'total_time_ms': ''},
                {'iteration': 'Sum', 'waiting_time_ms': waiting_time_sum,
                 'receiving_time_ms': receiving_time_sum,
                 'initiation_time_ms': initiation_time_sum,
                 'total_time_ms': total_time_sum}
            ]

            if valid_iterations > 0:
                summary_data.append({
                    'iteration': 'Average',
                    'waiting_time_ms': waiting_time_sum / valid_iterations,
                    'receiving_time_ms': receiving_time_sum / valid_iterations,
                    'initiation_time_ms': initiation_time_sum / valid_iterations,
                    'total_time_ms': total_time_sum / valid_iterations
                })
            else:
                summary_data.append({
                    'iteration': 'Average',
                    'waiting_time_ms': 'N/A',
                    'receiving_time_ms': 'N/A',
                    'initiation_time_ms': 'N/A',
                    'total_time_ms': 'N/A'
                })

            for row in summary_data:
                writer.writerow(row)

    except Exception as e:
        print(f"Error writing to CSV: {e}")

    # Print summary to console
    print(f"Summary: Valid iterations: {valid_iterations}")
    if valid_iterations > 0:
        print(
            f"Sum - Waiting: {waiting_time_sum:.2f}ms, Receiving: {receiving_time_sum:.2f}ms, Initiation: {initiation_time_sum:.2f}ms, Total: {total_time_sum:.2f}ms")
        print(
            f"Avg - Waiting: {waiting_time_sum / valid_iterations:.2f}ms, Receiving: {receiving_time_sum / valid_iterations:.2f}ms, Initiation: {initiation_time_sum / valid_iterations:.2f}ms, Total: {total_time_sum / valid_iterations:.2f}ms")
    else:
        print("No valid iterations found")

    # Always close the driver
    driver.quit()
    print(f"Test completed. Results saved to '{output_file}'")