import logging

def tag_with_privacy_and_metadata(data, user_id, contact_id=None, privacy_level="default"):
    """
    Tags the given data with user_id, contact_id, and privacy_level.

    Args:
        data (dict): The data to be tagged.
        user_id (str): The ID of the user associated with the data.
        contact_id (str, optional): The ID of the contact associated with the data. Defaults to None.
        privacy_level (str, optional): The privacy level of the data. Defaults to "default".

    Returns:
        dict: The tagged data.
    """
    try:
        tagged_data = {
            "user_id": user_id,
            "contact_id": contact_id,
            "privacy_level": privacy_level,
            **data
        }
        logging.info(f"Data tagged with privacy and metadata: {tagged_data}")
        return tagged_data
    except Exception as e:
        logging.error(f"Failed to tag data with privacy and metadata: {str(e)}")
        raise