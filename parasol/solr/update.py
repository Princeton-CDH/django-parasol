import json
from urllib.parse import urljoin


class Update:
    '''Class for managing the update handler functionality of the Solr API.'''
    def __init__(self, client, commit_within):
        self.client = client
        self.url = client.build_url(client.update_handler)
        self.headers = {'Content-Type': 'application/json'}
        self.params = {'commitWithin': commit_within}

    def index(self, docs, commit=False, commit_within=None):
        '''Index a document or documents, by default with a soft commit'''
        params = self.params.copy()
        if commit_within:
            params['commitWithin'] = commit_within
        # perform a hard commit, so remove commitWithin as superfluous
        # and set params.
        if commit:
            del params['commitWithin']
            params['commit'] = True
        url = urljoin('%s/' % self.url, 'json/docs')
        self.client.make_request(
            'post',
            url,
            data=docs,
            params=self.params,
            headers=self.headers
        )

    def _delete(self, del_obj):
        '''Private method to pass a delete object to the update handler.'''
        data = {'delete': del_obj}
        self.client.make_request(
            'post',
            self.url,
            data=data,
            params=self.params,
            headers=self.headers
        )

    def delete_by_id(self, id_list):
        self._delete(id_list)

    def delete_by_query(self, query):
        self._delete({'query': query})
