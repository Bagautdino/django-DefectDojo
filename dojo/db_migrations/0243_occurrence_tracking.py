from datetime import datetime

from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


def initialize_occurrence_metadata(apps, schema_editor):
    Finding = apps.get_model("dojo", "Finding")
    tz_utils = django.utils.timezone
    current_tz = tz_utils.get_current_timezone()

    for finding in Finding.objects.all().iterator():
        base_date = finding.date
        if isinstance(base_date, datetime):
            first_seen = tz_utils.make_aware(base_date, current_tz) if tz_utils.is_naive(base_date) else base_date
        elif base_date:
            first_seen = tz_utils.make_aware(datetime.combine(base_date, datetime.min.time()), current_tz)
        else:
            first_seen = tz_utils.now()

        last_seen = finding.last_seen or first_seen
        if tz_utils.is_naive(last_seen):
            last_seen = tz_utils.make_aware(last_seen, current_tz)

        if last_seen < first_seen:
            last_seen = first_seen

        finding.first_seen = first_seen
        finding.last_seen = last_seen
        if not finding.nb_occurrences:
            finding.nb_occurrences = 1
        finding.save(update_fields=["first_seen", "last_seen", "nb_occurrences"])


class Migration(migrations.Migration):
    dependencies = [
        ("dojo", "0242_file_upload_cleanup"),
    ]

    operations = [
        migrations.AddField(
            model_name="finding",
            name="first_seen",
            field=models.DateTimeField(
                default=django.utils.timezone.now,
                editable=False,
                help_text="Timestamp of the very first time this finding was recorded.",
                verbose_name="First Seen",
            ),
        ),
        migrations.AddField(
            model_name="finding",
            name="last_seen",
            field=models.DateTimeField(
                default=django.utils.timezone.now,
                editable=False,
                help_text="Timestamp of the most recent occurrence of this finding.",
                verbose_name="Last Seen",
            ),
        ),
        migrations.AddField(
            model_name="finding",
            name="nb_occurrences",
            field=models.PositiveIntegerField(
                default=1,
                editable=False,
                help_text="Number of times this finding signature has been observed.",
                verbose_name="Occurrences",
            ),
        ),
        migrations.CreateModel(
            name="FindingOccurrence",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("seen", models.DateTimeField(default=django.utils.timezone.now, help_text="Timestamp of this occurrence.", verbose_name="Seen")),
                ("scan_id", models.CharField(blank=True, help_text="Identifier of the source scan that produced this occurrence.", max_length=255, null=True, verbose_name="Scan Identifier")),
                ("raw_meta", models.JSONField(blank=True, default=dict, help_text="Arbitrary metadata captured for this occurrence.", verbose_name="Raw Metadata")),
                ("finding", models.ForeignKey(on_delete=models.deletion.CASCADE, related_name="occurrences", to="dojo.finding", verbose_name="Finding")),
                ("test", models.ForeignKey(blank=True, null=True, on_delete=models.deletion.CASCADE, related_name="finding_occurrences", to="dojo.test", verbose_name="Test")),
            ],
            options={
                "ordering": ("-seen", "finding"),
            },
        ),
        migrations.RunPython(
            code=initialize_occurrence_metadata,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.AddIndex(
            model_name="findingoccurrence",
            index=models.Index(fields=["finding", "seen"], name="dojo_findingoccurrence_find_seen_idx"),
        ),
        migrations.AddIndex(
            model_name="findingoccurrence",
            index=models.Index(fields=["test", "seen"], name="dojo_findingoccurrence_test_seen_idx"),
        ),
        migrations.AddIndex(
            model_name="finding",
            index=models.Index(fields=["hash_code", "false_p"], name="dojo_finding_hash_false_idx"),
        ),
        migrations.AddIndex(
            model_name="finding",
            index=models.Index(fields=["unique_id_from_tool", "false_p"], name="dojo_finding_uid_false_idx"),
        ),
        migrations.AlterField(
            model_name="system_settings",
            name="false_positive_history",
            field=models.BooleanField(
                default=False,
                help_text="DefectDojo will automatically mark the finding as a false positive if an equal finding (according to its dedupe algorithm) has been previously marked as a false positive on the same product. When used together with deduplication, repeated occurrences are counted without creating additional findings.",
            ),
        ),
        migrations.AlterField(
            model_name="system_settings",
            name="retroactive_false_positive_history",
            field=models.BooleanField(
                default=False,
                help_text="False Positive History will also retroactively mark/unmark all existing equal findings in the same product as false positives. Only works if the False Positive History feature is also enabled.",
            ),
        ),
]
