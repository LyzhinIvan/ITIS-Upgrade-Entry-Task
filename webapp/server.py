import os
import json
from datetime import datetime, timedelta
from flask import Flask, render_template, request
from pymongo import MongoClient

app = Flask(__name__)

client = MongoClient(host=os.getenv('MONGO_HOST', 'localhost'))
db = client.get_database('all_to_the_bottom')
categories = list(map(str, db.get_collection('actions').distinct('category', {'category': {'$ne': None}})))
category_names = [cat.capitalize().replace('_', ' ') for cat in categories]

@app.route('/')
def index():
    args = {}
    args['categories'] = dict(zip(categories, category_names)) 
    args['min_date'] = list(db.actions.find().sort([['at', 1]]).limit(1))[0]['at'].strftime('%Y-%m-%d')
    args['max_date'] = list(db.actions.find().sort([['at', -1]]).limit(1))[0]['at'].strftime('%Y-%m-%d')
    return render_template('index.html', **args)

@app.route('/actions_by_country')
def actions_by_country():
    actions = db.get_collection('actions')
    results = list(actions.aggregate([{
        '$match': {
            'country': { '$ne': None }
        }
    }, {
        '$group': {
            '_id': '$country', 
            'count': { '$sum': 1 }
        }
    }, {
        '$project': {
            'country': '$_id', 
            'count': '$count', 
            '_id': 0
        }
    }, {
        '$sort': {
            'count': -1
        }
    }]))
    return json.dumps(results)

@app.route('/interests_by_country', strict_slashes=False)
@app.route('/interests_by_country/<category>', strict_slashes=False)
def interests_by_country(category=None):
    actions = db.get_collection('actions')
    match_query = {
        'country': { '$ne': None }, 
        'action': 'get',
    }
    if str(category) != 'None':
        match_query['category'] = category
    results = list(actions.aggregate([{
        '$match': match_query
    }, {
        '$group': {
            '_id': '$country', 
            'count': { '$sum': 1 }
        }
    }, {
        '$project': {
            'country': '$_id', 
            'count': '$count', 
            '_id': 0
        }
    }, {
        '$sort': {
            'count': -1
        }
    }]))
    return json.dumps(results)

@app.route('/requests_by_time', strict_slashes=False)
def requests_by_time():
    actions = db.get_collection('actions')
    results = {
        'categories': {
            'ids': categories,
            'names': category_names
        }
    }
    for i, partOfDay in enumerate(['night', 'morning', 'afternoon', 'evening']):
        requests = db.actions.aggregate([{
            '$match': {
                'action': 'get', 
                '$expr': {
                    '$and': [
                        { '$gte': [{'$hour': '$at'}, i * 6] }, 
                        { '$lt': [{'$hour': '$at'}, (i + 1) * 6] }
                    ]
                }, 
                'category': { '$ne': None }
            }
        }, {
            '$group': {
                '_id': '$category', 
                'actions': { '$sum': 1 }
            }
        }, {
            '$project': {
                '_id': 0,
                'category': '$_id',
                'actions': 1
            }
        }])
        results[partOfDay] = {}
        for req in requests:
            results[partOfDay][req["category"]] = req["actions"]

    return json.dumps(results)

@app.route('/site_load')
def site_load():
    results = list(db.actions.aggregate([{
        '$project': {
            'at': { '$dateToString': {'format': '%G-%m-%d %H:00', 'date': '$at'} }
        }
    }, {
        '$group': {
            '_id': '$at', 
            'requests': {'$sum': 1}
        }
    }, {
        '$sort': {
            '_id': 1
        }
    }, {
        '$project': {
            'hour': '$_id', 
            'requests': 1, 
            '_id': 0
        }
    }]))
    return json.dumps(results)

def calc_relation_power(category, all_categories):
    cursor = db.get_collection('carts').aggregate([{
        '$project': {
            'has_category': { '$in': [category, '$goods.category']},
            'payed_at': 1,
            '_id': 0
        },
    }, {
        '$match': {
            'has_category': True,
            'payed_at': { '$ne': None }
        }
    }, {
        '$count': 'carts'
    }])
    carts_with_category = 0
    if cursor.alive:
        carts_with_category = cursor.next()['carts']
    results = {}
    if carts_with_category == 0:
        return results
    for related_category in all_categories:
        cursor = db.get_collection('carts').aggregate([{
            '$project': {
                'has_category': { '$in': [category, '$goods.category']},
                'has_related_category': { '$in': [related_category, '$goods.category']},
                'payed_at': 1,
                '_id': 0
            },
        }, {
            '$match': {
                'has_category': True,
                'has_related_category': True,
                'payed_at': { '$ne': None }
            }
        }, {
            '$count': 'carts'
        }])
        carts_with_two_categories = 0
        if cursor.alive:
            carts_with_two_categories = cursor.next()['carts']
        results[related_category] = carts_with_two_categories / carts_with_category
    return results

@app.route('/related_categories', strict_slashes=False)
def related_categories():
    results = {}
    for category in categories:
        results[category] = calc_relation_power(category, categories)
    return json.dumps(results)

@app.route('/aborted_carts')
def aborted_carts():
    start_date = request.args.get('start_date') or ''
    end_date = request.args.get('end_date') or ''
    query = {}
    if start_date != '' or end_date != '':
        query['$and'] = []
    if start_date != '':
        start_date = datetime.strptime(start_date, '%Y-%m-%d')
        query['$and'].append({'created_at': { '$gte': start_date }})
    if end_date != '':
        end_date = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(1)
        query['$and'].append({'created_at': { '$lt': end_date}})
    result = {}
    result['total'] = db.get_collection('carts').count(query)
    query['payed_at'] = None
    result['aborted'] = db.get_collection('carts').count(query)
    return json.dumps(result)

@app.route('/comeback_users')
def comeback_users():
    start_date = request.args.get('start_date') or ''
    end_date = request.args.get('end_date') or ''
    query = {
        'payed_at': { '$ne': None }
    }
    if start_date != '' or end_date != '':
        query['$and'] = []
    if start_date != '':
        start_date = datetime.strptime(start_date, '%Y-%m-%d')
        query['$and'].append({'payed_at': { '$gte': start_date }})
    if end_date != '':
        end_date = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(1)
        query['$and'].append({'payed_at': { '$lt': end_date}})
    match_query = {}
    aggregate_query = [{
        '$match': query,
    }, {
        '$group': {
            '_id': '$user_id',
            'purchases': { '$sum': 1 }
        },
    }, {
        '$match': match_query
    }, {
        '$count': 'users'
    }]
    result = { 'total': 0, 'comeback': 0 }
    cursor = db.get_collection('carts').aggregate(aggregate_query)
    if cursor.alive:
        result['total'] = cursor.next()['users']
    match_query['purchases'] = {'$gt': 1}
    cursor = db.get_collection('carts').aggregate(aggregate_query)
    if cursor.alive:
        result['comeback'] = cursor.next()['users']
    return json.dumps(result)