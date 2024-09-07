from django.shortcuts import render, redirect
from multiprocessing import JoinableQueue as Queue
from threading import Thread
from django.contrib.auth.decorators import login_required
import requests
from bs4 import BeautifulSoup
from rq import Queue as rQueue
from worker import conn
import uuid
from rq.job import Job
from rq import get_current_job
import json
from rq.exceptions import NoSuchJobError
import logging
import time
from django.http import JsonResponse

logger = logging.getLogger(__name__)

q = rQueue(connection=conn)


class Web_spider():
    def __init__(self):
        self.visited_or_about_to_visit = set()
        self.web_links = Queue()
        self.baseurl = 'https://sites.research.unimelb.edu.au/research-funding'
        self.broken_link_file = open('broken_links_faster.txt', 'w')
        self.UOM_sign_links = list()
        self.uom_sign_link_file = open('uom_links.txt','w')
        self.keyword_link_file = open('keyword_links.txt','w')
        self.counter = 0
        self.broken_links = list()
        self.keyword = 'Funding Partners'
        self.keyword_links = list()

    def put_url(self, baseurl):
        # [link, source page link, associated text]
        self.web_links.put([baseurl, None, None])
        self.counter += 1
        self.baseurl = baseurl

    def put_keyword(self, keyword):
        self.keyword = keyword

    def is_uom_sign_link(self, link):
        return self.baseurl in link
    
    def add_uom_sign_link(self, link, source_link):
        self.UOM_sign_links.append({'url': link, 'source_link': source_link})

    def write_uom_sign_link(self, link, source_link):
        self.uom_sign_link_file.write(f'uom link:{link}, page source:{source_link}\n')

    def deal_uom_sign_link(self, link, source_link):
        if self.is_uom_sign_link(link):
            self.add_uom_sign_link(link, source_link)
            self.write_uom_sign_link(link, source_link)
    def add_broken_link(self, link, source_link, associated_text):
        self.broken_links.append({'url': link, 'source_link':
            source_link, 'associated_text': associated_text})

    def write_broken_link(self, link, source_link, response_status, associated_text):
        self.broken_link_file.write(f'status:{response_status}, broken link: '
                                    f'{link}, page source: {source_link}, associated_text: {associated_text}\n')

    def deal_broken_link(self, link, source_link, response_status, associated_text):
        self.add_broken_link(link, source_link, associated_text)
        self.write_broken_link(link, source_link, response_status, associated_text)

    def get_more_links(self):
        while True:
            link_combo = self.web_links.get()

            link = link_combo[0]
            try:
                print(f'getting link {link}')
                response = requests.get(link, timeout=2)
                self.visited_or_about_to_visit.add(link)
                if response.status_code == 200:
                    if not link.startswith(self.baseurl):
                        continue
                    soup = BeautifulSoup(response.content, 'html.parser')
                    if self.keyword is not None:
                        text = soup.get_text()
                        if self.keyword in text:
                            print(f'found keyword {self.keyword} in link {link}')
                            self.keyword_links.append(link)
                            self.keyword_link_file.write(link + '\n')
                    for href_link in soup.find_all('a', href=True):
                        href = href_link['href']
                        text = href_link.get_text()
                        if href not in self.visited_or_about_to_visit:
                            if 'mailto:' not in href:
                                self.visited_or_about_to_visit.add(href)
                                self.web_links.put([href, link, text])
                                self.counter += 1
                                # Enqueue a new job for the found link
                                # q.enqueue('process_link', href, link)
                            else:
                                print(f'not responsible for checking mails {href}')
                            print('new links founded', href)
                else:
                    if response.status_code == 403:
                        self.deal_uom_sign_link(link, link_combo[1])
                    else:
                        self.deal_broken_link(link, link_combo[1], response.status_code, link_combo[2])
                    print(f'status_code:{response.status_code}, broken_link:{link}, page source:{link_combo[1]}, associated_text:{link_combo[2]}')

                    # print(f'now the queue size is {self.web_links.qsize()}')
            except requests.exceptions.Timeout:
                print(f'timeout fetching {link}')
                self.deal_broken_link(link, link_combo[1], 'timeout', link_combo[2])
            except Exception as e:
                print(f'error fetch {link}, {str(e)}')
            finally:
                self.web_links.task_done()
                self.counter -= 1
                print(f'Final counter = {self.counter}')
                print(f'remaining links number {self.web_links.qsize()}')

    # help save time by filtering out broken link to reduce response time
    def detect_links(self):
        while True:
            link_combo = self.web_links.get()
            link = link_combo[0]

            try:
                print(f'detecting link {link}')
                response = requests.get(link, timeout = 2)
                # if not broken, then put back to the queue
                if response.status_code == 200:
                    if link.startswith(self.baseurl):
                        self.web_links.put(link_combo)
                        self.counter += 1
                    else:
                        if self.counter == 0:
                            print('finished')
                            return
                else:
                    print(f'status_code:{response.status_code}, broken_link:{link}, page source:{link_combo[1]}')
                    if response.status_code == 403:
                        self.deal_uom_sign_link(link, link_combo[1])
                    else:
                        self.deal_broken_link(link, link_combo[1], response.status_code, link_combo[2])

            except Exception as e:
                print(f'error fetch {link}, {str(e)}')
            finally:
                self.web_links.task_done()
                self.counter -= 1

                print(f'counter = {self.counter}')
                # print(f'remaining detected tasks{self.web_links.qsize()}')

                 # Check if the queue is empty and counter is zero to break the loop
                if self.web_links.qsize() == 0 and self.counter == 0:
                    print('finished')
                    get_current_job().set_status('finished')
                    break

    def search_broken_links(self, baseurl):
        self.put_url(baseurl)
        thread_list = list()
        for _ in range(20):
            t = Thread(target=self.get_more_links)
            thread_list.append(t)
        for _ in range(20):
            t = Thread(target=self.detect_links)
            thread_list.append(t)
        for t in thread_list:
            t.daemon = True
            t.start()
        for t in thread_list:
            t.join()
        self.web_links.join()
        print(self.keyword_links)
        return self.broken_links
    def search_keyword_links(self, baseurl, keyword):
        self.put_keyword(keyword)
        self.put_url(baseurl)
        thread_list = list()
        for _ in range(20):
            t = Thread(target=self.get_more_links)
            thread_list.append(t)
        for _ in range(20):
            t = Thread(target=self.detect_links)
            thread_list.append(t)
        for t in thread_list:
            t.daemon = True
            t.start()
        self.web_links.join()
        return self.keyword_links

# def process_link(href, source_url):
#     try:
#         print(f'Processing link {href} from source {source_url}')
#         response = requests.get(href)
#         if response.status_code == 200:
#             print(f'Link {href} is valid.')
#         else:
#             print(f'Link {href} is broken with status code {response.status_code}.')
#             # Handle broken link (e.g., log it, save it to a file, etc.)
#     except Exception as e:
#         print(f'Error processing link {href}: {str(e)}')

@login_required
def search_link(request):
    q.empty()
    if request.method == 'POST':
        try:
            url = request.POST.get('url')
            keyword = request.POST.get('keyword')  # Fetch the keyword if it's provided

            job_id = str(uuid.uuid4())

            # Enqueue the job in the background
            job = Job.create('apps.search_link.views.search_task', id=job_id, connection=conn, args=(url, keyword, job_id))
            q.enqueue_job(job)
            logger.error(f"Checking job {job.id}")
            logger.error(f"Job {job.id} status: {job.get_status()}")

            # Poll the job every second for up to 30 seconds
            for i in range(60):
                time.sleep(0.5)
                job.refresh()
                logger.error(f"Job {job.id} status after refresh: {job.get_status()}")
                logger.error(f"Job {job.id} job position: {job.get_position()}")
                if job.is_finished:
                    break
            return redirect('results', job_id=job.id)

        except ConnectionError as e:
            logger.error(f"Redis connection error: {str(e)}")
            return render(request, 'results.html', {'error': 'Could not connect to Redis. Please try again later.'})
        except Exception as e:
            logger.error(f"Error in search_link view: {str(e)}")
            return render(request, 'results.html', {'error': str(e)})
    return render(request, 'search.html')

# assign a job ID to each task
def search_task(url, keyword, job_id):
    job_id = str(job_id) # ensure job_id is a string
    # Initialize Web_spider instance
    web_spider = Web_spider()

    if keyword:
        results = web_spider.search_keyword_links(url, keyword)
    else:
        results = web_spider.search_broken_links(url)
    
    # Serialize the results as a JSON string
    results_json = json.dumps(results)

    # Store the results in a Redis key using the job ID
    conn.set(job_id, results_json, ex=3600) # Results expire after 1 hour

# def results(request, job_id):
#     logger.info(f"Fetching results for job_id: {job_id}")
#     try:
#         job = q.fetch_job(str(job_id))
#         while not job.is_finished and not job.is_failed:
#             time.sleep(1)
#             job.refresh()
#             logger.debug(f"Job {job_id} status after refresh: {job.get_status()}")

#         if job.is_finished:
#             results = conn.get(str(job_id))
#             if results:
#                 results = json.loads(results)
#             else:
#                 results = []
#             logger.info(f"Job {job_id} finished successfully with results.")
#             return render(request, 'results.html', {'results': results, 'job_id': job_id})
#         elif job.is_failed:
#             logger.error(f"Job {job_id} failed.")
#             return render(request, 'results.html', {'error': 'Job failed.', 'job_id': job_id})
#     except NoSuchJobError:
#         logger.error(f"No such job found: {job_id}")
#         return render(request, 'results.html', {'error': '!!No such job found.', 'job_id': job_id})
#     except ConnectionError as e:
#         logger.error(f"Redis connection error: {str(e)}")
#         return render(request, 'results.html', {'error': 'Could not connect to Redis. Please try again later.', 'results': [], 'job_id': job_id})
#     except Exception as e:
#         logger.error(f"Error fetching results for job {job_id}: {str(e)}")
#         return render(request, 'results.html', {'error': str(e), 'results': [], 'job_id': job_id})
    
def results(request, job_id):
    job_id = str(job_id) # ensure job_id is a string
    logger.info(f"Fetching results for job_id: {job_id}")
    
    try:
        # Poll for the job for up to 30 seconds
        job = None
        for i in range(60):
            job = q.fetch_job(job_id)
            if job is not None:
                break
            time.sleep(0.5)
            if i % 10 == 0:
                logger.warning(f"Job {job_id} not found after {i*0.5} seconds")
        
        if job is None:
            logger.warning(f"No job found for job_id: {job_id} after polling")
            return render(request, 'results.html', {'error': 'Job not found', 'job_id': job_id})
        
        status = job.get_status()
        
        if status == 'finished':
            results = conn.get(job_id)
            if results:
                results = json.loads(results)
            else:
                results = []
            return render(request, 'results.html', {'results': results, 'job_id': job_id})
        elif status == 'failed':
            return render(request, 'results.html', {'error': 'Job failed', 'job_id': job_id})
        else:
            return render(request, 'results.html', {'status': 'pending', 'job_id': job_id})
    
    except NoSuchJobError:
        logger.error(f"No such job found: {job_id}")
        return render(request, 'results.html', {'error': 'Job not found', 'job_id': job_id})
    except Exception as e:
        logger.error(f"Error fetching results for job {job_id}: {str(e)}")
        return render(request, 'results.html', {'error': str(e), 'job_id': job_id})

def job_status(request, job_id):
    job_id = str(job_id) # ensure job_id is a string
    logger.info(f"Checking job status for job_id: {job_id}")
    try:
        job = Job.fetch(str(job_id), connection=conn)
        if job.is_finished:
            logger.info(f"Job {job_id} is finished.")
            return JsonResponse({'status': 'finished'})
        elif job.is_failed:
            logger.error(f"Job {job_id} has failed.")
            return JsonResponse({'status': 'failed'})
        else:
            logger.info(f"Job {job_id} is still running.")
            return JsonResponse({'status': 'running'})
    except NoSuchJobError:
        logger.error(f"No such job found: {job_id}")
        return JsonResponse({'status': 'not_found'})
    except Exception as e:
        logger.error(f"Error checking job status for job {job_id}: {str(e)}")
        return JsonResponse({'status': 'error', 'message': str(e)})