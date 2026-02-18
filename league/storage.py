from django.core.files.storage import Storage
from django.core.files.base import ContentFile
import cloudinary
import cloudinary.uploader
import cloudinary.api
import os


class CloudinaryStorage(Storage):
    """Custom Cloudinary storage backend"""
    
    def _save(self, name, content):
        """Save file to Cloudinary"""
        folder = os.path.dirname(name)
        result = cloudinary.uploader.upload(
            content,
            folder=folder,
            resource_type='auto'
        )
        # Return the public_id as the "name" for retrieval
        return result['public_id']
    
    def url(self, name):
        """Return Cloudinary URL for the file"""
        if not name:
            return ''
        # Use cloudinary.CloudinaryImage to generate the proper URL
        return cloudinary.CloudinaryImage(name).build_url()
    
    def exists(self, name):
        """Check if file exists in Cloudinary"""
        if not name:
            return False
        try:
            cloudinary.api.resource(name)
            return True
        except Exception:
            return False
    
    def delete(self, name):
        """Delete file from Cloudinary"""
        if not name:
            return
        try:
            cloudinary.uploader.destroy(name)
        except Exception:
            pass
    
    def size(self, name):
        """Get file size"""
        if not name:
            return 0
        try:
            resource = cloudinary.api.resource(name)
            return resource.get('bytes', 0)
        except Exception:
            return 0
