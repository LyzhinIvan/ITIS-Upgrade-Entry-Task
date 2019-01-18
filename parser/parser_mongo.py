import os
import re
from argparse import ArgumentParser
from datetime import datetime
from pymongo import MongoClient
import geoip2.database

DB_NAME = 'all_to_the_bottom'

class Ip2CountryMapper:
    def __init__(self):
        self.db = geoip2.database.Reader('GeoLite2-Country.mmdb')
    
    def country(self, ip, default=None):
        try:
            country = self.db.country(ip)
            return country.country.names['en']
        except:
            return default


def get_url_args(url):
    if url.find('?') == -1:
        return {}
    url = url[url.find('?')+1:]
    return dict(map(lambda arg: arg.split('='), url.split('&')))


def main():
    arg_parser = ArgumentParser()
    arg_parser.add_argument('--logs-file', type=str, default='logs.txt')
    args = arg_parser.parse_args()

    client = MongoClient(host=os.getenv('MONGO_HOST', 'localhost'))
    client.drop_database(DB_NAME)
    db = client.get_database(DB_NAME)
    actions = db.get_collection("actions")
    carts = db.get_collection("carts")

    last_visit = dict()
    ip_mapper = Ip2CountryMapper()
    regexp = re.compile(r'^shop_api      \| (\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) \[\w+\] INFO: (\d{1,3}\.\d{1,3}.\d{1,3}.\d{1,3}) https://all_to_the_bottom.com(.*)')
    with open(args.logs_file, "r") as logs_file:
        for line in logs_file.readlines():
            action_time, ip, url = regexp.findall(line.strip())[0]
            action_time = datetime.strptime(action_time, '%Y-%m-%d %H:%M:%S')
            country = ip_mapper.country(ip)
            url_args = get_url_args(url)
            action = {
                'ip': ip,
                'country': country,
                'at': action_time,
                'action': 'cart',
            }
            action.update(url_args)
            if url.startswith('/cart'):
                action['type'] = 'cart'
                actions.insert_one(action)
                if carts.find_one({'id': action['cart_id']}) is None:
                    carts.insert_one({
                        'id': action['cart_id'],
                        'created_at': action['at'],
                        'goods': []
                    })
                carts.update_one({
                    'id': action['cart_id']
                }, {
                    '$push': {
                        'goods': {
                            'good': last_visit[ip][1],
                            'category': last_visit[ip][0],
                            'amount': action['amount']
                        }
                    }
                })

            elif url.startswith('/pay'):
                action['type'] = 'pay'
                actions.insert_one(action)
                carts.update_one({
                    'id': action['cart_id']
                }, {
                    '$set': {
                        'user_id': action['user_id']
                    }
                }, upsert=True)

            elif url.startswith('/success_pay'):
                action['type'] = 'success_pay'
                action['cart_id'] = url[url.rfind('_')+1:-1]
                actions.insert_one(action)
                carts.update_one({
                    'id': action['cart_id']
                }, {
                    '$set': {
                        'payed_at': action['at']
                    }
                }, upsert=True)

            else:
                url_parts = url.split('/')
                category = url_parts[1] if len(url_parts) > 2 else None
                good = url_parts[2] if len(url_parts) > 3 else None
                action['action'] = 'get'
                action['category'] = category
                action['good'] = good
                actions.insert_one(action)
                last_visit[ip] = (category, good)
    client.close()


if __name__ == "__main__":
    main()