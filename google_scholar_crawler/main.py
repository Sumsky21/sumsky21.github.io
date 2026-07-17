from scholarly import scholarly
import jsonpickle
import json
from datetime import datetime
import os
import time

# 添加重试逻辑和超时处理
max_retries = 3
retry_count = 0

while retry_count < max_retries:
    try:
        print(f"Attempt {retry_count + 1}/{max_retries} to fetch Google Scholar data...")
        author: dict = scholarly.search_author_id(os.environ['GOOGLE_SCHOLAR_ID'])
        
        # 添加延迟以避免被Google限制
        time.sleep(2)
        
        scholarly.fill(author, sections=['basics', 'indices', 'counts', 'publications'])
        name = author['name']
        author['updated'] = str(datetime.now())
        author['publications'] = {v['author_pub_id']:v for v in author['publications']}
        print(json.dumps(author, indent=2))
        os.makedirs('results', exist_ok=True)
        with open(f'results/gs_data.json', 'w') as outfile:
            json.dump(author, outfile, ensure_ascii=False)

        shieldio_data = {
          "schemaVersion": 1,
          "label": "citations",
          "message": f"{author['citedby']}",
        }
        with open(f'results/gs_data_shieldsio.json', 'w') as outfile:
            json.dump(shieldio_data, outfile, ensure_ascii=False)
        
        print("Successfully fetched and saved Google Scholar data!")
        break
    except Exception as e:
        retry_count += 1
        print(f"Error on attempt {retry_count}: {str(e)}")
        if retry_count < max_retries:
            wait_time = 5 * retry_count  # 指数退避
            print(f"Retrying in {wait_time} seconds...")
            time.sleep(wait_time)
        else:
            print("Max retries exceeded. Using cached data if available.")
            # 如果有缓存的数据，可以使用它
            if os.path.exists('results/gs_data.json'):
                print("Using cached Google Scholar data...")
            else:
                raise

