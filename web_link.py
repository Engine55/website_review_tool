# the program print links not accessible with the source page it appears on
# also with the status code of those responses failed, written to a file named
# broken_links.txt, while it takes too long time to run, the next step would be
# using threading pool or process pool or some async functions to speed up searching
# and also need to classify the type of response not with status code 200 or 404
# to see why it failed
import requests
from bs4 import BeautifulSoup
broken_links = list()
def scrape_pages(baseurl):
    # the file used to record the broken links and its parent links
    with open('broken_links.txt', 'w') as f:
        visited_or_about_to_visit = set()
        to_visit_list = list()
        # base url don't have parent in pattern [current link, source page link]
        to_visit_list.append([baseurl,None])
        while to_visit_list:
            url_combo = to_visit_list.pop(0)
            url = url_combo[0]
            try:
                response = requests.get(url)
                visited_or_about_to_visit.add(url)
                if response.status_code == 200:
                    # for external links just need to check its accessibility, no need to find sublink
                    if not url.startswith(baseurl):
                        continue
                    soup = BeautifulSoup(response.content, 'html.parser')
                    for link in soup.find_all('a', href=True):
                        href = link['href']
                        if href not in visited_or_about_to_visit:

                            visited_or_about_to_visit.add(href)
                            to_visit_list.append([href,url])

                            print('new links founded', href)
                else:
                    print(f'broken link{url} founded with status {response.status_code}')
                    print()
                    broken_links.append(url)
                    f.write('broken link is ' + url + '  page source url is ' + url_combo[1] + '  status_code: ' + str(response.status_code) + '\n')
            except requests.exceptions.RequestException as e:

                print(f"Error fetching {url}: {e}")
base_url = 'https://sites.research.unimelb.edu.au/research-funding'

scrape_pages(base_url)