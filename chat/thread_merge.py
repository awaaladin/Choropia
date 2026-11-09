from django.db import transaction


def conversation_merge_plan(apps):
    Conversation = apps.get_model("chat", "Conversation")
    groups = {}
    for conversation in Conversation.objects.order_by("created_at", "pk").iterator():
        pair = tuple(sorted((conversation.buyer_id, conversation.seller_id)))
        groups.setdefault(pair, []).append(conversation)
    return [(pair, rows[0], rows[1:]) for pair, rows in groups.items() if len(rows) > 1]


@transaction.atomic
def merge_conversations(apps, *, dry_run=False, write=None):
    Conversation = apps.get_model("chat", "Conversation")
    Message = apps.get_model("chat", "Message")
    Offer = apps.get_model("offers", "Offer")
    plans = conversation_merge_plan(apps)
    report = []

    for (low_id, high_id), keeper, duplicates in plans:
        duplicate_ids = [row.pk for row in duplicates]
        message_count = Message.objects.filter(conversation_id__in=duplicate_ids).count()
        offer_count = Offer.objects.filter(conversation_id__in=duplicate_ids).count()
        legacy_order_ids = [row.order_id for row in [keeper, *duplicates] if row.order_id]
        order_count = len(set(legacy_order_ids))
        report.append(
            {
                "pair": (low_id, high_id),
                "keeper": keeper.pk,
                "duplicates": duplicate_ids,
                "messages": message_count,
                "offers": offer_count,
                "orders": order_count,
            }
        )
        if dry_run:
            continue

        keeper.user_low_id = low_id
        keeper.user_high_id = high_id
        if keeper.order_id is None and legacy_order_ids:
            keeper.order_id = legacy_order_ids[0]
        keeper.save(update_fields=["user_low", "user_high", "order"])

        for order_id in legacy_order_ids:
            keeper.orders.add(order_id)
        Message.objects.filter(conversation_id__in=duplicate_ids).update(conversation_id=keeper.pk)
        Offer.objects.filter(conversation_id__in=duplicate_ids).update(conversation_id=keeper.pk)

        Notification = apps.get_model("notifications", "Notification")
        ContentType = apps.get_model("contenttypes", "ContentType")
        conversation_type = ContentType.objects.get_for_model(Conversation)
        Notification.objects.filter(
            target_content_type=conversation_type,
            target_object_id__in=duplicate_ids,
        ).update(target_object_id=keeper.pk)

        Conversation.objects.filter(pk__in=duplicate_ids).delete()

    if dry_run:
        if write:
            for row in report:
                write(row)
        return report

    for conversation in Conversation.objects.all().iterator():
        pair = sorted((conversation.buyer_id, conversation.seller_id))
        if (conversation.user_low_id, conversation.user_high_id) != tuple(pair):
            conversation.user_low_id, conversation.user_high_id = pair
            conversation.save(update_fields=["user_low", "user_high"])
        if conversation.order_id:
            conversation.orders.add(conversation.order_id)

    if write:
        for row in report:
            write(row)
    return report
