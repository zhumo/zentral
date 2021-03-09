from datetime import datetime
from unittest.mock import patch
import uuid
from django.urls import reverse
from django.test import TestCase, override_settings
from django.utils.crypto import get_random_string
from accounts.models import User
from zentral.contrib.osquery.models import (DistributedQuery, DistributedQueryMachine, DistributedQueryResult,
                                            FileCarvingSession, Query)


@override_settings(STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage')
class OsquerySetupDistributedQueriesViewsTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user("godzilla", "godzilla@zentral.io", get_random_string())

    # utiliy methods

    def _login_redirect(self, url):
        response = self.client.get(url)
        self.assertRedirects(response, "{u}?next={n}".format(u=reverse("login"), n=url))

    def _force_distributed_query(self):
        query = self._force_query()
        return DistributedQuery.objects.create(
            query=query,
            query_version=query.version,
            sql=query.sql,
            valid_from=datetime.utcnow(),
        )

    def _force_query(self):
        return Query.objects.create(name=get_random_string(), sql="select 1 from processes;")

    # create distributed query

    def test_create_distributed_query_redirect(self):
        query = self._force_query()
        self._login_redirect("{}?q={}".format(reverse("osquery:create_distributed_query"), query.pk))

    def test_create_distributed_query_get(self):
        query = self._force_query()
        self.client.force_login(self.user)
        response = self.client.get("{}?q={}".format(reverse("osquery:create_distributed_query"), query.pk))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "osquery/distributedquery_form.html")
        self.assertContains(response, "Launch query")
        self.assertContains(response, query.name)

    def test_create_distributed_query_post(self):
        query = self._force_query()
        self.client.force_login(self.user)
        response = self.client.post(
            "{}?q={}".format(reverse("osquery:create_distributed_query"), query.pk),
            {"valid_from": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
             "shard": "100"},
            follow=True
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "osquery/distributedquery_detail.html")
        self.assertEqual(response.context["query"], query)
        distributed_query = response.context["object"]
        self.assertEqual(distributed_query.query, query)
        self.assertEqual(distributed_query.sql, query.sql)
        self.assertEqual(distributed_query.query_version, query.version)

    def test_create_distributed_query_valid_until_less_than_valid_from(self):
        query = self._force_query()
        self.client.force_login(self.user)
        response = self.client.post(
            "{}?q={}".format(reverse("osquery:create_distributed_query"), query.pk),
            {"valid_from": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
             "valid_until": "2021-02-18 20:55:00",
             "shard": "100"},
            follow=True
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "osquery/distributedquery_form.html")
        self.assertContains(response, "Valid until must be greater than valid from")

    def test_create_distributed_query_valid_until_past(self):
        query = self._force_query()
        self.client.force_login(self.user)
        response = self.client.post(
            "{}?q={}".format(reverse("osquery:create_distributed_query"), query.pk),
            {"valid_from": "2020-07-30 11:50:00",
             "valid_until": "2021-02-18 20:55:00",
             "shard": "100"},
            follow=True
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "osquery/distributedquery_form.html")
        self.assertContains(response, "Valid until is in the past")

    # update distributed query

    def test_update_distributed_query_redirect(self):
        distributed_query = self._force_distributed_query()
        self._login_redirect(reverse("osquery:update_distributed_query", args=(distributed_query.pk,)))

    def test_update_distributed_query_get(self):
        distributed_query = self._force_distributed_query()
        self.client.force_login(self.user)
        response = self.client.get(reverse("osquery:update_distributed_query", args=(distributed_query.pk,)))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "osquery/distributedquery_form.html")
        self.assertEqual(response.context["object"], distributed_query)

    def test_update_distributed_query_post(self):
        distributed_query = self._force_distributed_query()
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("osquery:update_distributed_query", args=(distributed_query.pk,)),
            {"valid_from": "2020-07-30 11:50:00",
             "valid_until": "2021-02-18 20:55:00",
             "shard": "99"},
            follow=True
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "osquery/distributedquery_detail.html")
        self.assertEqual(response.context["object"], distributed_query)
        distributed_query.refresh_from_db()
        self.assertEqual(distributed_query.shard, 99)

    def test_update_distributed_query_valid_until_less_than_valid_from(self):
        distributed_query = self._force_distributed_query()
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("osquery:update_distributed_query", args=(distributed_query.pk,)),
            {"valid_from": "2021-02-18 20:55:00",
             "valid_until": "2020-07-30 11:50:00",
             "shard": "99"},
            follow=True
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "osquery/distributedquery_form.html")
        self.assertEqual(response.context["object"], distributed_query)
        self.assertContains(response, "Valid until must be greater than valid from")

    # distributed query list

    def test_distributed_queries_redirect(self):
        self._login_redirect(reverse("osquery:distributed_queries"))

    def test_distributed_queries_get(self):
        distributed_query = self._force_distributed_query()
        self.client.force_login(self.user)
        response = self.client.get(reverse("osquery:distributed_queries"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "osquery/distributedquery_list.html")
        self.assertContains(response, distributed_query.query.name)

    # distributed query

    def test_distributed_query_redirect(self):
        distributed_query = self._force_distributed_query()
        self._login_redirect(reverse("osquery:distributed_query", args=(distributed_query.pk,)))

    def test_distributed_query(self):
        distributed_query = self._force_distributed_query()
        self.client.force_login(self.user)
        response = self.client.get(reverse("osquery:distributed_query", args=(distributed_query.pk,)))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "osquery/distributedquery_detail.html")
        self.assertEqual(response.context["object"], distributed_query)

    # delete distributed query

    def test_delete_distributed_query_redirect(self):
        distributed_query = self._force_distributed_query()
        self._login_redirect(reverse("osquery:delete_distributed_query", args=(distributed_query.pk,)))

    def test_delete_distributed_query_get(self):
        distributed_query = self._force_distributed_query()
        self.client.force_login(self.user)
        response = self.client.get(reverse("osquery:delete_distributed_query", args=(distributed_query.pk,)))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "osquery/distributedquery_confirm_delete.html")
        self.assertEqual(response.context["object"], distributed_query)

    def test_delete_distributed_query_post(self):
        distributed_query = self._force_distributed_query()
        self.client.force_login(self.user)
        response = self.client.post(reverse("osquery:delete_distributed_query", args=(distributed_query.pk,)),
                                    follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "osquery/distributedquery_list.html")
        self.assertNotIn(distributed_query, response.context["object_list"])

    # distributed query machines

    def test_distributed_query_machines_redirect(self):
        distributed_query = self._force_distributed_query()
        self._login_redirect(reverse("osquery:distributed_query_machines", args=(distributed_query.pk,)))

    @patch("zentral.contrib.osquery.views.distributed_queries.DistributedQueryMachineListView.get_paginate_by")
    def test_distributed_query_machines(self, get_paginate_by):
        get_paginate_by.return_value = 1
        distributed_query = self._force_distributed_query()
        dqm_count = 3
        serial_numbers = [get_random_string() for _ in range(dqm_count)]
        err_msgs = [get_random_string() for _ in range(dqm_count)]
        dqm_gen = (
            DistributedQueryMachine(
                distributed_query=distributed_query,
                serial_number=serial_numbers[i],
                status=3,
                error_message=err_msgs[i],
            ) for i in range(dqm_count)
        )
        DistributedQueryMachine.objects.bulk_create(dqm_gen)
        self.client.force_login(self.user)
        response = self.client.get(reverse("osquery:distributed_query_machines", args=(distributed_query.pk,)))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "osquery/distributedquerymachine_list.html")
        self.assertContains(response, f"{dqm_count} Machines")
        self.assertContains(response, serial_numbers[-1])
        self.assertContains(response, "Error")
        self.assertContains(response, err_msgs[-1])

    # distributed query results

    def test_distributed_query_results_redirect(self):
        distributed_query = self._force_distributed_query()
        self._login_redirect(reverse("osquery:distributed_query_results", args=(distributed_query.pk,)))

    @patch("zentral.contrib.osquery.views.distributed_queries.DistributedQueryResultListView.get_paginate_by")
    def test_distributed_query_results(self, get_paginate_by):
        get_paginate_by.return_value = 1
        distributed_query = self._force_distributed_query()
        dqr_count = 4
        serial_numbers = [get_random_string() for _ in range(dqr_count)]
        dqr_gen = (
            DistributedQueryResult(
                distributed_query=distributed_query,
                serial_number=serial_numbers[i],
                row={"un": get_random_string()}
            ) for i in range(dqr_count)
        )
        DistributedQueryResult.objects.bulk_create(dqr_gen)
        self.client.force_login(self.user)
        response = self.client.get(reverse("osquery:distributed_query_results", args=(distributed_query.pk,)))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "osquery/distributedqueryresult_list.html")
        self.assertContains(response, f"{dqr_count} Results")
        self.assertContains(response, serial_numbers[-1])
        self.assertContains(response, "<th>un</th>")
        self.assertContains(response, f"page 1 of {dqr_count}")

    # distributed query file carving sessions

    def test_distributed_query_file_carving_sessions_redirect(self):
        distributed_query = self._force_distributed_query()
        self._login_redirect(reverse("osquery:distributed_query_file_carving_sessions", args=(distributed_query.pk,)))

    @patch("zentral.contrib.osquery.views.distributed_queries."
           "DistributedQueryFileCarvingSessionListView.get_paginate_by")
    def test_distributed_query_file_carving_sessions(self, get_paginate_by):
        get_paginate_by.return_value = 1
        distributed_query = self._force_distributed_query()
        fcs_count = 5
        serial_numbers = [get_random_string() for _ in range(fcs_count)]
        fcs_gen = (
            FileCarvingSession(
                id=uuid.uuid4(),
                distributed_query=distributed_query,
                serial_number=serial_numbers[i],
                carve_guid=str(uuid.uuid4()),
                block_size=8472,
                block_count=17,
                carve_size=8499,
            ) for i in range(fcs_count)
        )
        FileCarvingSession.objects.bulk_create(fcs_gen)
        self.client.force_login(self.user)
        response = self.client.get(reverse("osquery:distributed_query_file_carving_sessions",
                                           args=(distributed_query.pk,)))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "osquery/dq_filecarvingsession_list.html")
        self.assertContains(response, f"{fcs_count} File carving sessions")
        self.assertContains(response, serial_numbers[-1])
        self.assertContains(response, "0/17")
        self.assertContains(response, f"page 1 of {fcs_count}")
