SELECT
	snap_key_iv.snap_id AS 'SNAP ID',
	snap_address_title.address_title AS 'Region',
	snap_location_table.latitude AS 'Latitude',
	snap_location_table.longitude AS 'Longitude',
	snap_key_iv.key AS 'Key',
	snap_key_iv.iv AS 'IV'
FROM 
	snap_key_iv
LEFT JOIN
	snap_location_table ON snap_key_iv.snap_id = snap_location_table.snap_id
LEFT JOIN
	snap_address_title ON snap_address_title.snap_id = snap_key_iv.snap_id;