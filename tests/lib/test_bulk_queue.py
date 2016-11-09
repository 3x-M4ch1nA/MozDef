import time

import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), "../../lib"))
from bulk_queue import BulkQueue

from query_models import SearchQuery, ExistsMatch

sys.path.append(os.path.join(os.path.dirname(__file__), "../"))
from unit_test_suite import UnitTestSuite


class BulkQueueTest(UnitTestSuite):
    def setup(self):
        super(BulkQueueTest, self).setup()

    def num_objects_saved(self):
        self.es_client.flush('events')
        search_query = SearchQuery()
        search_query.add_must(ExistsMatch('keyname'))
        results = search_query.execute(self.es_client)
        return len(results['hits'])


class TestBasicInit(BulkQueueTest):

    def setup(self):
        super(TestBasicInit, self).setup()
        self.queue = BulkQueue(self.es_client)

    def test_threshold(self):
        assert self.queue.threshold == 10

    def test_size(self):
        assert self.queue.size() == 0

    def test_flush_time(self):
        assert self.queue.flush_time == 30


class TestInitWithThreshold(BulkQueueTest):

    def test_init_with_threshold(self):
        queue = BulkQueue(self.es_client, 100)
        assert queue.threshold == 100


class TestAdd(BulkQueueTest):

    def setup(self):
        super(TestAdd, self).setup()
        self.queue = BulkQueue(self.es_client, threshold=20)

    def test_basic_add(self):
        assert self.queue.size() == 0
        self.queue.add(index='events', doc_type='event', body={'keyname', 'valuename'})
        assert self.queue.size() == 1
        assert self.queue.started() is False

    def test_add_exact_threshold(self):
        for num in range(0, 20):
            self.queue.add(index='events', doc_type='event', body={'keyname': 'value' + str(num)})
        assert self.queue.size() == 0
        assert self.num_objects_saved() == 20
        assert self.queue.started() is False

    def test_add_over_threshold(self):
        for num in range(0, 21):
            self.queue.add(index='events', doc_type='event', body={'keyname': 'value' + str(num)})
        assert self.num_objects_saved() == 20
        assert self.queue.size() == 1
        assert self.queue.started() is False

    def test_add_multiple_thresholds(self):
        for num in range(0, 201):
            self.queue.add(index='events', doc_type='event', body={'keyname': 'value' + str(num)})
        assert self.num_objects_saved() == 200
        assert self.queue.size() == 1
        assert self.queue.started() is False


class TestTimer(BulkQueueTest):

    def test_basic_timer(self):
        queue = BulkQueue(self.es_client, flush_time=2)
        assert queue.started() is False
        queue.start_timer()
        assert queue.started() is True
        queue.add(index='events', doc_type='event', body={'keyname': 'valuename'})
        assert queue.size() == 1
        time.sleep(3)
        assert queue.size() == 0
        queue.stop_timer()
        assert queue.started() is False

    def test_over_threshold(self):
        queue = BulkQueue(self.es_client, flush_time=3, threshold=10)
        queue.start_timer()
        for num in range(0, 201):
            queue.add(index='events', doc_type='event', body={'keyname': 'value' + str(num)})
        assert self.num_objects_saved() == 200
        assert queue.size() == 1
        time.sleep(4)
        assert self.num_objects_saved() == 201
        assert queue.size() == 0
        queue.stop_timer()

    def test_two_iterations(self):
        queue = BulkQueue(self.es_client, flush_time=3, threshold=10)
        queue.start_timer()
        for num in range(0, 201):
            queue.add(index='events', doc_type='event', body={'keyname': 'value' + str(num)})
        assert self.num_objects_saved() == 200
        assert queue.size() == 1
        time.sleep(5)
        assert self.num_objects_saved() == 201
        assert queue.size() == 0
        for num in range(0, 201):
            queue.add(index='events', doc_type='event', body={'keyname': 'value' + str(num)})
        assert self.num_objects_saved() == 401
        time.sleep(5)
        assert self.num_objects_saved() == 402
        queue.stop_timer()

    def test_ten_iterations(self):
        queue = BulkQueue(self.es_client, flush_time=3, threshold=10)
        queue.start_timer()
        total_events = 0
        for num_rounds in range(0, 10):
            for num in range(0, 20):
                total_events += 1
                queue.add(index='events', doc_type='event', body={'keyname': 'value' + str(num)})
            assert self.num_objects_saved() == total_events
        assert queue.size() == 0
        queue.stop_timer()
        assert self.num_objects_saved() == 200


# todo: add tests for what if inserting events goes bad? bad data? can't connect to ES?
