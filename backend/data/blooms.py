import datetime

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from data.connection import db_cursor
from data.users import User


@dataclass
class Bloom:
    id: int
    sender: User
    content: str
    sent_timestamp: datetime.datetime
    original_bloom_id: Optional[int] =None 
    original_sender: Optional[str] = None    
    rebloom_count: int = 0       


def add_bloom(*, sender: User, content: str, original_bloom_id: Optional[int] = None) -> Bloom:
    hashtags = [word[1:] for word in content.split(" ") if word.startswith("#")]

    now = datetime.datetime.now(tz=datetime.UTC)
    bloom_id = int(now.timestamp() * 1000000)
    with db_cursor() as cur:
        cur.execute(
            "INSERT INTO blooms (id, sender_id, content, send_timestamp, original_bloom_id) VALUES (%(bloom_id)s, %(sender_id)s, %(content)s, %(timestamp)s, %(original_bloom_id)s)",
            dict(
                bloom_id=bloom_id,
                sender_id=sender.id,
                content=content,
                timestamp=datetime.datetime.now(datetime.UTC),
                original_bloom_id=original_bloom_id,
            ),
        )
        for hashtag in hashtags:
            cur.execute(
                "INSERT INTO hashtags (hashtag, bloom_id) VALUES (%(hashtag)s, %(bloom_id)s)",
                dict(hashtag=hashtag, bloom_id=bloom_id),
            )
    return Bloom(id=bloom_id, sender=sender.username, content=content, sent_timestamp=now, original_bloom_id=original_bloom_id)


def get_blooms_for_user(
    username: str, *, before: Optional[int] = None, limit: Optional[int] = None
) -> List[Bloom]:
    with db_cursor() as cur:
        kwargs = {
            "sender_username": username,
        }
        if before is not None:
            before_clause = "AND send_timestamp < %(before_limit)s"
            kwargs["before_limit"] = before
        else:
            before_clause = ""

        limit_clause = make_limit_clause(limit, kwargs)
        cur.execute(
            f"""SELECT
              b.id,
              u.username,
              b.content,
              b.send_timestamp,
              b.original_bloom_id,
              ou.username AS original_sender,
              (SELECT COUNT(*) FROM blooms WHERE original_bloom_id = COALESCE(b.original_bloom_id, b.id)) AS rebloom_count
            FROM blooms b
            INNER JOIN users u ON u.id = b.sender_id
            LEFT JOIN blooms ob ON b.original_bloom_id = ob.id
            LEFT JOIN users ou ON ob.sender_id = ou.id
            WHERE
              u.username = %(sender_username)s
              {before_clause}
            ORDER BY b.send_timestamp DESC
            {limit_clause}
            """,
            kwargs,
        )
        rows = cur.fetchall()
        blooms = []
        for row in rows:
            bloom_id, sender_username, content, timestamp, original_bloom_id, original_sender, rebloom_count = row
            blooms.append(
                Bloom(
                    id=bloom_id,
                    sender=sender_username,
                    content=content,
                    sent_timestamp=timestamp,
                    original_bloom_id=original_bloom_id,
                    original_sender=original_sender,
                    rebloom_count=rebloom_count,
                )
            )
    return blooms


def get_bloom(bloom_id: int) -> Optional[Bloom]:
    with db_cursor() as cur:
        cur.execute(
            "SELECT b.id, u.username, b.content, b.send_timestamp, b.original_bloom_id, ou.username AS original_sender, (SELECT COUNT(*) FROM blooms WHERE original_bloom_id = COALESCE(b.original_bloom_id, b.id)) AS rebloom_count FROM blooms b INNER JOIN users u ON u.id = b.sender_id LEFT JOIN blooms ob ON b.original_bloom_id = ob.id LEFT JOIN users ou ON ob.sender_id = ou.id WHERE b.id = %s",
            (bloom_id,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        bloom_id, sender_username, content, timestamp, original_bloom_id, original_sender, rebloom_count = row
        return Bloom(
            id=bloom_id,
            sender=sender_username,
            content=content,
            sent_timestamp=timestamp,
            original_bloom_id=original_bloom_id,
            original_sender=original_sender,
            rebloom_count=rebloom_count,
        )


def get_blooms_with_hashtag(
    hashtag_without_leading_hash: str, *, limit: int = None
) -> List[Bloom]:
    kwargs = {
        "hashtag_without_leading_hash": hashtag_without_leading_hash,
    }
    limit_clause = make_limit_clause(limit, kwargs)
    with db_cursor() as cur:
        cur.execute(
            f"""SELECT
              b.id,
              u.username,
              b.content,
              b.send_timestamp,
              b.original_bloom_id,
              ou.username AS original_sender,
              (SELECT COUNT(*) FROM blooms WHERE original_bloom_id = COALESCE(b.original_bloom_id, b.id)) AS rebloom_count
            FROM blooms b
            INNER JOIN hashtags ON b.id = hashtags.bloom_id INNER JOIN users u ON b.sender_id = u.id
            LEFT JOIN blooms ob ON b.original_bloom_id = ob.id
            LEFT JOIN users ou ON ob.sender_id = ou.id
            WHERE
              hashtag = %(hashtag_without_leading_hash)s
            ORDER BY b.send_timestamp DESC
            {limit_clause}
            """,
            kwargs,
        )
        rows = cur.fetchall()
        blooms = []
        for row in rows:
            bloom_id, sender_username, content, timestamp, original_bloom_id, original_sender, rebloom_count = row
            blooms.append(
                Bloom(
                    id=bloom_id,
                    sender=sender_username,
                    content=content,
                    sent_timestamp=timestamp,
                    original_bloom_id=original_bloom_id,
                    original_sender=original_sender,
                    rebloom_count=rebloom_count,
                )
            )
    return blooms


def make_limit_clause(limit: Optional[int], kwargs: Dict[Any, Any]) -> str:
    if limit is not None:
        limit_clause = "LIMIT %(limit)s"
        kwargs["limit"] = limit
    else:
        limit_clause = ""
    return limit_clause
