from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from dojo.models import (
    Finding,
    Product_Type,
    Test_Type,
)

from .dojo_test_case import DojoTestCase


class FindingOccurrenceTrackingTests(DojoTestCase):
    def setUp(self):
        super().setUp()
        self.system_settings(
            enable_deduplication=True,
            false_positive_history=True,
            retroactive_false_positive_history=True,
        )

        self.product_type, _ = Product_Type.objects.get_or_create(name="Occurrence Product")
        self.product = self.create_product("Occurrence Product", prod_type=self.product_type)
        self.engagement = self.create_engagement("Occurrence Engagement", self.product)

        self.test_type, _ = Test_Type.objects.get_or_create(
            name="Occurrence Scan",
            defaults={"dynamic_tool": False, "static_tool": True},
        )

        self._original_dedupe_mapping = getattr(settings, "DEDUPLICATION_ALGORITHM_PER_PARSER", {}).copy()
        new_mapping = self._original_dedupe_mapping.copy()
        new_mapping[self.test_type.name] = settings.DEDUPE_ALGO_HASH_CODE
        settings.DEDUPLICATION_ALGORITHM_PER_PARSER = new_mapping

        self.test = self.create_test(
            engagement=self.engagement,
            scan_type=self.test_type.name,
            title="Occurrence Scan",
        )

    def tearDown(self):
        settings.DEDUPLICATION_ALGORITHM_PER_PARSER = self._original_dedupe_mapping
        super().tearDown()

    def _create_finding(self, title="Recurring Finding"):
        finding = Finding(
            test=self.test,
            title=title,
            severity="High",
            description="Sample description",
            mitigation="Mitigation instructions",
            impact="Impact details",
            references="",
        )
        finding.save()
        return finding

    def test_duplicate_occurrence_increases_counter(self):
        initial = self._create_finding()
        self.assertEqual(initial.nb_occurrences, 1)

        previous_last_seen = initial.last_seen
        second = self._create_finding()

        self.assertFalse(Finding.objects.filter(pk=second.pk).exists())
        initial.refresh_from_db()
        self.assertEqual(initial.nb_occurrences, 2)
        self.assertGreaterEqual(initial.last_seen, previous_last_seen)
        self.assertEqual(initial.occurrences.count(), 1)

    def test_false_positive_occurrence_merges(self):
        initial = self._create_finding()
        initial.false_p = True
        initial.active = False
        initial.save(dedupe_option=False, rules_option=False, issue_updater_option=False, product_grading_option=False)

        second = self._create_finding()

        self.assertFalse(Finding.objects.filter(pk=second.pk).exists())
        initial.refresh_from_db()
        self.assertTrue(initial.false_p)
        self.assertEqual(initial.nb_occurrences, 2)

    def test_last_seen_updates_when_reimported(self):
        initial = self._create_finding()
        initial.last_seen = timezone.now() - timedelta(days=7)
        initial.save(dedupe_option=False, rules_option=False, issue_updater_option=False, product_grading_option=False)

        later = self._create_finding()

        self.assertFalse(Finding.objects.filter(pk=later.pk).exists())
        initial.refresh_from_db()
        self.assertGreater(initial.last_seen, timezone.now() - timedelta(days=1))
        self.assertEqual(initial.nb_occurrences, 2)
        self.assertEqual(initial.occurrences.count(), 1)
