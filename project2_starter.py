# SI 201 HW4 (Library Checkout System)
# Your name: Mehr Takkar
# Your student id: 2062 2272
# Your email: mtakkar@umich.edu
# Who or what you worked with on this homework (including generative AI like ChatGPT):
# If you worked with generative AI also add a statement for how you used it.
# I used claude to help me when I was debugging. I also needed help with creating lambdas.
#
# Did your use of GenAI on this assignment align with your goals and guidelines in your Gen AI contract? If not, why?
#Yes I did not use it as a clutch but to enhance my learning. 

# --- ARGUMENTS & EXPECTED RETURN VALUES PROVIDED --- #
# --- SEE INSTRUCTIONS FOR FULL DETAILS ON METHOD IMPLEMENTATION --- #

from bs4 import BeautifulSoup
import re
import os
import csv
import unittest
import requests  # kept for extra credit parity


# IMPORTANT NOTE:
"""
If you are getting "encoding errors" while trying to open, read, or write from a file, add the following argument to any of your open() functions:
    encoding="utf-8-sig"
"""


def load_listing_results(html_path) -> list[tuple]:
    """
    Load file data from html_path and parse through it to find listing titles and listing ids.

    Args:
        html_path (str): The path to the HTML file containing the search results

    Returns:
        list[tuple]: A list of tuples containing (listing_title, listing_id)
    """
    # TODO: Implement checkout logic following the instructions
    # ==============================
    # YOUR CODE STARTS HERE
    # ==============================
    # Open and parse the search results HTML file
    with open(html_path, encoding="utf-8-sig") as f:
        soup = BeautifulSoup(f, "html.parser")
 
    results = []
    seen_ids = set()  # track IDs we've already added so we don't duplicate
 
    # Every listing on the search page has an <a> tag whose href contains /rooms/ or /rooms/plus/
    # We find all such links, then extract the numeric ID from the URL
    for link in soup.find_all("a", href=re.compile(r"/rooms/")):
        href = link.get("href", "")
 
        # The URL looks like /rooms/1944564?... or /rooms/plus/16204265?...
        # This regex captures the numeric ID in either case
        match = re.search(r"/rooms/(?:plus/)?(\d+)", href)
        if not match:
            continue
 
        listing_id = match.group(1)
 
        # Skip if we've already seen this ID (each listing appears in multiple <a> tags)
        if listing_id in seen_ids:
            continue
        seen_ids.add(listing_id)
 
        # The title lives in a tag whose id starts with "title_" inside the same card.
        # Walk up the DOM until we find a parent that contains a title_ element.
        title = None
        parent = link.find_parent("div")
        while parent:
            title_tag = parent.find(id=re.compile(r"^title_"))
            if title_tag:
                title = title_tag.get_text(strip=True)
                break
            parent = parent.find_parent("div")
 
        if title:  # only add if we successfully found a title
            results.append((title, listing_id))
 
    return results
    # ==============================
    # YOUR CODE ENDS HERE
    # ==============================


def get_listing_details(listing_id) -> dict:
    """
    Parse through listing_<id>.html to extract listing details.

    Args:
        listing_id (str): The listing id of the Airbnb listing

    Returns:
        dict: Nested dictionary in the format:
        {
            "<listing_id>": {
                "policy_number": str,
                "host_type": str,
                "host_name": str,
                "room_type": str,
                "location_rating": float
            }
        }
    """
    # TODO: Implement checkout logic following the instructions
    # ==============================
    # YOUR CODE STARTS HERE
    # ==============================
    
    # Build the path to the individual listing file.
    # The html_files folder sits next to this script.
    base_dir = os.path.abspath(os.path.dirname(__file__))
    file_path = os.path.join(base_dir, "html_files", f"listing_{listing_id}.html")
 
    with open(file_path, encoding="utf-8-sig") as f:
        soup = BeautifulSoup(f, "html.parser")
 
 
    # POLICY NUMBER 
    # The page has a <li> that literally starts with "Policy number: "
    # followed by a <span> containing the actual value.
    policy_number = "Exempt"  # default if nothing is found
 
    policy_tag = soup.find(string=lambda t: t and "Policy number" in t)
    if policy_tag:
        # The span immediately inside the same <li> holds the raw value
        span = policy_tag.parent.find("span")
        if span:
            raw = span.get_text(strip=True)
 
            # Normalize to the three allowed categories.
            # Some hosts type "pending" (lowercase), so we compare case-insensitively.
            if raw.lower() == "pending":
                policy_number = "Pending"
            elif raw.lower() == "exempt":
                policy_number = "Exempt"
            else:
                # Strip any hidden BOM/whitespace characters that sneak in
                policy_number = raw.strip()
 
    # HOST TYPE 
    # If the word "Superhost" appears anywhere on the page the host is a Superhost.
    # We check for a <span> that contains exactly "Superhost".
    superhost_tag = soup.find(string=lambda t: t and t.strip() == "Superhost")
    host_type = "Superhost" if superhost_tag else "regular"
 
    # HOST NAME
    # The heading "Hosted by <Name>" always appears in an <h2> tag.
    host_name = ""
    hosted_tag = soup.find("h2", string=lambda t: t and "Hosted by" in t)
    if hosted_tag:
        # Remove "Hosted by " prefix to get just the name(s)
        host_name = hosted_tag.get_text(strip=True).replace("Hosted by ", "").strip()
    else:
        # Fallback: some pages put the text in a different tag
        for tag in soup.find_all(string=lambda t: t and "Hosted by" in str(t) and "{" not in str(t)):
            text = tag.strip()
            if "Hosted by" in text and len(text) < 100:
                host_name = text.replace("Hosted by", "").strip()
                break
            
            
    # ROOM TYPE
    # The subtitle of the listing (e.g. "Entire loft hosted by Brian" or
    # "Private room in home hosted by John") tells us the room type.
    # We classify based on whether "Private" or "Shared" appears in that subtitle.
    room_type = "Entire Room"  # default
 
    for tag in soup.find_all(string=lambda t: t and (
        "Entire" in str(t) or "Private" in str(t) or "Shared" in str(t)
    )):
        s = str(tag).strip()
        # Only look at short subtitle-like strings (not long review text)
        if len(s) < 150:
            if "Private" in s:
                room_type = "Private Room"
            elif "Shared" in s:
                room_type = "Shared Room"
            else:
                room_type = "Entire Room"
            break  # first match is the subtitle; stop here
 
    # LOCATION RATING
    # Ratings are displayed in a section where "Location" label sits in a div,
    # and the numeric score sits in the very next sibling div inside a <span
    # aria-hidden="true">.
    location_rating = 0.0  # default when no rating exists
 
    for tag in soup.find_all(string=lambda t: t and t.strip() == "Location"):
        parent = tag.parent
        next_sib = parent.find_next_sibling()
        if next_sib:
            # The score number is in a <span aria-hidden="true"> e.g. "4.9"
            score_span = next_sib.find("span", {"aria-hidden": "true"})
            if score_span:
                try:
                    location_rating = float(score_span.get_text(strip=True))
                    break  # found it, no need to keep looking
                except ValueError:
                    pass  # not a number, keep searching
 
    # Build and return the nested dictionary the instructions require
    return {
        listing_id: {
            "policy_number": policy_number,
            "host_type": host_type,
            "host_name": host_name,
            "room_type": room_type,
            "location_rating": location_rating,
        }
    }
    # ==============================
    # YOUR CODE ENDS HERE
    # ==============================


def create_listing_database(html_path) -> list[tuple]:
    """
    Use prior functions to gather all necessary information and create a database of listings.

    Args:
        html_path (str): The path to the HTML file containing the search results

    Returns:
        list[tuple]: A list of tuples. Each tuple contains:
        (listing_title, listing_id, policy_number, host_type, host_name, room_type, location_rating)
    """
    # TODO: Implement checkout logic following the instructions
    # ==============================
    # YOUR CODE STARTS HERE
    # ==============================
    # get the (title, id) pairs from the search results page
    listings = load_listing_results(html_path)
 
    database = []
 
    for listing_title, listing_id in listings:
        # get the detailed info dict for this listing
        details_dict = get_listing_details(listing_id)
 
        # details_dict looks like: { "1944564": { "policy_number": ..., ... } }
        details = details_dict[listing_id]
 
        # pack everything in single flat tuple in the required order
        row = (
            listing_title,
            listing_id,
            details["policy_number"],
            details["host_type"],
            details["host_name"],
            details["room_type"],
            details["location_rating"],
        )
        database.append(row)
 
    return database
    # ==============================
    # YOUR CODE ENDS HERE
    # ==============================


def output_csv(data, filename) -> None:
    """
    Write data to a CSV file with the provided filename.

    Sort by Location Rating (descending).

    Args:
        data (list[tuple]): A list of tuples containing listing information
        filename (str): The name of the CSV file to be created and saved to

    Returns:
        None
    """
    # TODO: Implement checkout logic following the instructions
    # ==============================
    # YOUR CODE STARTS HERE
    # ==============================
    
    # Sort a copy of data by location_rating (index 6) from highest to lowest.
    # We use a copy so we don't modify the original list passed in.
    sorted_data = sorted(data, key=lambda row: row[6], reverse=True)
 
    with open(filename, "w", newline="", encoding="utf-8-sig") as csv_file:
        writer = csv.writer(csv_file)
 
        # Write the header row first
        writer.writerow([
            "Listing Title",
            "Listing ID",
            "Policy Number",
            "Host Type",
            "Host Name",
            "Room Type",
            "Location Rating",
        ])
 
        # Write each listing as its own row
        for row in sorted_data:
            writer.writerow(row)
    # ==============================
    # YOUR CODE ENDS HERE
    # ==============================


def avg_location_rating_by_room_type(data) -> dict:
    """
    Calculate the average location_rating for each room_type.

    Excludes rows where location_rating == 0.0 (meaning the rating
    could not be found in the HTML).

    Args:
        data (list[tuple]): The list returned by create_listing_database()

    Returns:
        dict: {room_type: average_location_rating}
    """
    # TODO: Implement checkout logic following the instructions
    # ==============================
    # YOUR CODE STARTS HERE
    # ==============================
    
    # accumulate (total_rating, count) per room type, then divide at the end.
    # Using a regular dict means we have to check if the key exists yet each time.
    totals = {}   # room_type -> running sum of ratings
    counts = {}   # room_type -> number of ratings added
 
    for row in data:
        room_type = row[5]       # index 5 = room_type
        location_rating = row[6] # index 6 = location_rating
 
        # Skip listings with no rating (stored as 0.0)
        if location_rating == 0.0:
            continue
 
        # Initialize the room type bucket if first time seeing it
        if room_type not in totals:
            totals[room_type] = 0.0
            counts[room_type] = 0
 
        totals[room_type] += location_rating
        counts[room_type] += 1
 
    # Compute the average for each room type and round to 1 decimal place
    averages = {}
    for room_type in totals:
        averages[room_type] = round(totals[room_type] / counts[room_type], 1)
 
    return averages
    # ==============================
    # YOUR CODE ENDS HERE
    # ==============================


def validate_policy_numbers(data) -> list[str]:
    """
    Validate policy_number format for each listing in data.
    Ignore "Pending" and "Exempt" listings.

    Args:
        data (list[tuple]): A list of tuples returned by create_listing_database()

    Returns:
        list[str]: A list of listing_id values whose policy numbers do NOT match the valid format
    """
    # TODO: Implement checkout logic following the instructions
    # ==============================
    # YOUR CODE STARTS HERE
    # ==============================
    # The two valid formats are:
    #   20##-00####STR   e.g. 2022-004088STR
    #   STR-000####      e.g. STR-0005349
    # '#' means any digit 0-9.
    
    valid_pattern = re.compile(
        r"^20\d{2}-00\d{4}STR$"   # format 1: 20##-00####STR
        r"|"
        r"^STR-000\d{4}$"         # format 2: STR-000####
    )
 
    invalid_ids = []
 
    for row in data:
        listing_id = row[1]       # index 1 = listing_id
        policy_number = row[2]    # index 2 = policy_number
 
        # Skip listings explicitly marked as Pending or Exempt
        if policy_number in ("Pending", "Exempt"):
            continue
 
        # If the policy number doesn't match either valid pattern, flag it
        if not valid_pattern.match(policy_number):
            invalid_ids.append(listing_id)
 
    return invalid_ids
    # ==============================
    # YOUR CODE ENDS HERE
    # ==============================


# EXTRA CREDIT
def google_scholar_searcher(query):
    """
    EXTRA CREDIT

    Args:
        query (str): The search query to be used on Google Scholar
    Returns:
        List of titles on the first page (list)
    """
    # TODO: Implement checkout logic following the instructions
    # ==============================
    # YOUR CODE STARTS HERE
    # ==============================
    
    # Build the Google Scholar search URL with the query encoded for a URL
    url = f"https://scholar.google.com/scholar?q={query.replace(' ', '+')}"
 
    # Send an HTTP GET request pretending to be a browser (some sites block plain requests)
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)
 
    soup = BeautifulSoup(response.text, "html.parser")
 
    # Each result title is inside an <h3> with class "gs_rt"
    titles = []
    for h3 in soup.find_all("h3", class_="gs_rt"):
        # The <h3> may contain nested <a> or <span> tags; get_text() strips them all
        titles.append(h3.get_text(strip=True))
 
    return titles
    # ==============================
    # YOUR CODE ENDS HERE
    # ==============================


class TestCases(unittest.TestCase):
    def setUp(self):
        self.base_dir = os.path.abspath(os.path.dirname(__file__))
        self.search_results_path = os.path.join(self.base_dir, "html_files", "search_results.html")

        self.listings = load_listing_results(self.search_results_path)
        self.detailed_data = create_listing_database(self.search_results_path)

    def test_load_listing_results(self):
        # Check that exactly 18 listings were extracted
        self.assertEqual(len(self.listings), 18)
 
        # Check that the very first tuple matches the expected title and ID
        self.assertEqual(self.listings[0], ("Loft in Mission District", "1944564"))

    def test_get_listing_details(self):
        html_list = ["467507", "1550913", "1944564", "4614763", "6092596"]
 
        # Call get_listing_details() on each ID and collect the result dicts
        results = [get_listing_details(lid) for lid in html_list]
 
        # 1) listing 467507 should have policy number "STR-0005349"
        self.assertEqual(results[0]["467507"]["policy_number"], "STR-0005349")
 
        # 2) listing 1944564 should be a Superhost with room type "Entire Room"
        self.assertEqual(results[2]["1944564"]["host_type"], "Superhost")
        self.assertEqual(results[2]["1944564"]["room_type"], "Entire Room")
 
        # 3) listing 1944564 should have a location rating of 4.9
        self.assertEqual(results[2]["1944564"]["location_rating"], 4.9)

    def test_create_listing_database(self):
        # Every tuple must have exactly 7 elements
        for row in self.detailed_data:
            self.assertEqual(len(row), 7)
 
        # The last tuple should match this known value
        expected_last = (
            "Guest suite in Mission District",
            "467507",
            "STR-0005349",
            "Superhost",
            "Jennifer",
            "Entire Room",
            4.8,
        )
        self.assertEqual(self.detailed_data[-1], expected_last)

    def test_output_csv(self):
        out_path = os.path.join(self.base_dir, "test.csv")
 
        # Write the CSV
        output_csv(self.detailed_data, out_path)
 
        # Read it back in
        rows = []
        with open(out_path, encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            next(reader)  # skip the header row
            for row in reader:
                rows.append(row)
 
        # The first DATA row (highest location_rating) should be Ingrid's guesthouse at 5.0
        expected_first = [
            "Guesthouse in San Francisco",
            "49591060",
            "STR-0000253",
            "Superhost",
            "Ingrid",
            "Entire Room",
            "5.0",
        ]
        self.assertEqual(rows[0], expected_first)
 
        os.remove(out_path)

    def test_avg_location_rating_by_room_type(self):
        # TODO: Call avg_location_rating_by_room_type() and save the output.
        # TODO: Check that the average for "Private Room" is 4.9.
        pass

    def test_validate_policy_numbers(self):
        # TODO: Call validate_policy_numbers() on detailed_data and save the result into a variable invalid_listings.
        # TODO: Check that the list contains exactly "16204265" for this dataset.
        pass


def main():
    detailed_data = create_listing_database(os.path.join("html_files", "search_results.html"))
    output_csv(detailed_data, "airbnb_dataset.csv")


if __name__ == "__main__":
    main()
    unittest.main(verbosity=2)