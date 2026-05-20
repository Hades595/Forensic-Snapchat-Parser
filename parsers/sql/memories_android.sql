SELECT 
    memories_media._id AS media_id,
    memories_snap._id AS snap_id,
    memories_media.format,
    memories_media.download_url,
	memories_snap.longitude,
	memories_snap.latitude,
	memories_snap.media_key,
	memories_snap.media_iv
FROM memories_snap
JOIN memories_media 
    ON memories_snap.media_id = memories_media._id;