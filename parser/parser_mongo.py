import os
import re
from argparse import ArgumentParser
from datetime import datetime
from pymongo import MongoClient
import geoip2.database

DB_NAME = 'all_to_the_bottom'

class Ip2CountryMapper:
    def __init__(self):
        base_path = os.path.dirname(os.path.realpath(__file__))
        ip_database_path = os.path.join(base_path, 'GeoLite2-Country.mmdb')
        self.db = geoip2.database.Reader(ip_database_path)
    
    def country(self, ip, default=None):
        try:
            info = self.db.country(ip)
            return info.country.names['en']
        except:
            return default

class IpTracker:
    def __init__(self):
        self.last_page = {}

    def visit(self, ip, page):
        self.last_page[ip] = page

    def get_last_page(self, ip):
        return self.last_page[ip]


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

    ip_tracker = IpTracker()
    ip_mapper = Ip2CountryMapper()
    regexp = re.compile(r'^shop_api      \| (\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) \[\w+\] INFO: (\d{1,3}\.\d{1,3}.\d{1,3}.\d{1,3}) https://all_to_the_bottom.com(.*)')
    with open(args.logs_file, "r") as logs_file:
        for line in logs_file:
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
                category, good = ip_tracker.get_last_page(ip)
                carts.update_one({
                    'id': action['cart_id']
                }, {
                    '$push': {
                        'goods': {
                            'good': good,
                            'category': category,
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
                ip_tracker.visit(ip, (category, good))
    client.close()


if __name__ == "__main__":
    main()