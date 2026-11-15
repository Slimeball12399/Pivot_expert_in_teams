from django.contrib import admin

from .models import File, FullVoiceResult, PartialVoiceResult, Session, Talk


class TalkInline(admin.TabularInline):
    model = Talk
    fields = ["status", "started_at", "duration", "audio"]
    extra = 0
    show_change_link = True


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ["id", "speaker", "trainer", "status", "display", "scheduled_at", "started_at", "ended_at"]
    list_filter = ["status", "display"]
    inlines = [TalkInline]


@admin.register(Talk)
class TalkAdmin(admin.ModelAdmin):
    list_display = ["id", "session", "status", "started_at", "duration"]
    list_filter = ["status"]


@admin.register(File)
class FileAdmin(admin.ModelAdmin):
    list_display = ["key", "kind", "content_type", "size_bytes", "uploaded_at", "created_at"]
    list_filter = ["kind"]
    search_fields = ["key"]


@admin.register(PartialVoiceResult)
class PartialVoiceResultAdmin(admin.ModelAdmin):
    list_display = ["talk", "start_at", "window_length", "voiced_seconds", "voice_score"]


@admin.register(FullVoiceResult)
class FullVoiceResultAdmin(admin.ModelAdmin):
    list_display = ["talk", "voice_score", "created_at"]
