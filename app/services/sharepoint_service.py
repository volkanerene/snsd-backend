"""
SharePoint Service for syncing incident report PDFs
"""
import os
from typing import List, Dict, Any, Optional
from datetime import datetime
import asyncio
import aiohttp


class SharePointService:
    """Service for interacting with SharePoint to fetch incident reports"""

    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id
        # SharePoint credentials should be stored in tenant settings
        # For now, use environment variables
        self.sharepoint_site_url = os.getenv("SHAREPOINT_SITE_URL")
        self.sharepoint_folder_path = os.getenv("SHAREPOINT_INCIDENT_REPORTS_FOLDER", "/Shared Documents/Incident Reports")
        self.client_id = os.getenv("SHAREPOINT_CLIENT_ID")
        self.client_secret = os.getenv("SHAREPOINT_CLIENT_SECRET")
        self.tenant_name = os.getenv("SHAREPOINT_TENANT_NAME")

    async def get_access_token(self) -> Optional[str]:
        """Get OAuth access token for SharePoint API"""
        if not all([self.client_id, self.client_secret, self.tenant_name]):
            return None

        token_url = f"https://accounts.accesscontrol.windows.net/{self.tenant_name}/tokens/OAuth/2"

        data = {
            'grant_type': 'client_credentials',
            'client_id': f'{self.client_id}@{self.tenant_name}',
            'client_secret': self.client_secret,
            'resource': f'00000003-0000-0ff1-ce00-000000000000/{self.sharepoint_site_url.split("//")[1].split("/")[0]}@{self.tenant_name}'
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(token_url, data=data) as response:
                    if response.status == 200:
                        result = await response.json()
                        return result.get('access_token')
                    return None
        except Exception as e:
            print(f"Error getting SharePoint access token: {str(e)}")
            return None

    async def list_pdf_files(self) -> List[Dict[str, Any]]:
        """List all PDF files from SharePoint folder"""
        access_token = await self.get_access_token()
        if not access_token:
            # Return mock data for development
            return self._get_mock_files()

        # Real SharePoint API call
        api_url = f"{self.sharepoint_site_url}/_api/web/GetFolderByServerRelativeUrl('{self.sharepoint_folder_path}')/Files"

        headers = {
            'Authorization': f'Bearer {access_token}',
            'Accept': 'application/json;odata=verbose'
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        files = []

                        for item in data.get('d', {}).get('results', []):
                            if item.get('Name', '').lower().endswith('.pdf'):
                                files.append({
                                    'id': item.get('UniqueId'),
                                    'name': item.get('Name'),
                                    'url': f"{self.sharepoint_site_url}{item.get('ServerRelativeUrl')}",
                                    'size': item.get('Length'),
                                    'modified': item.get('TimeLastModified'),
                                    'created': item.get('TimeCreated')
                                })

                        return files
                    return []
        except Exception as e:
            print(f"Error listing SharePoint files: {str(e)}")
            return self._get_mock_files()

    async def download_file(self, file_url: str) -> Optional[bytes]:
        """Download a file from SharePoint"""
        access_token = await self.get_access_token()
        if not access_token:
            return None

        headers = {
            'Authorization': f'Bearer {access_token}'
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(file_url, headers=headers) as response:
                    if response.status == 200:
                        return await response.read()
                    return None
        except Exception as e:
            print(f"Error downloading SharePoint file: {str(e)}")
            return None

    def _get_mock_files(self) -> List[Dict[str, Any]]:
        """Return mock files for development/testing"""
        mock_files = []

        for i in range(1, 11):  # 10 mock files as sample
            mock_files.append({
                'id': f'mock-file-{i}',
                'name': f'Incident_Report_{i:03d}.pdf',
                'url': f'https://mock.sharepoint.com/incident_{i}.pdf',
                'size': 1024 * (50 + i * 10),  # Random sizes
                'modified': datetime.now().isoformat(),
                'created': datetime.now().isoformat()
            })

        return mock_files

    async def sync_incident_reports(self, callback=None) -> Dict[str, Any]:
        """
        Sync incident reports from SharePoint to database

        Args:
            callback: Optional callback function to report progress

        Returns:
            Dict with sync results
        """
        from app.db.supabase_client import supabase

        results = {
            'total_found': 0,
            'new_files': 0,
            'updated_files': 0,
            'failed': 0,
            'errors': []
        }

        try:
            # List all PDF files
            files = await self.list_pdf_files()
            results['total_found'] = len(files)

            if callback:
                await callback('listing_complete', results['total_found'])

            # Process each file
            for idx, file_info in enumerate(files):
                try:
                    # Check if file already exists
                    existing = supabase.table("marcel_gpt_incident_reports") \
                        .select("id, last_modified") \
                        .eq("sharepoint_id", file_info['id']) \
                        .execute()

                    if existing.data and len(existing.data) > 0:
                        # File exists - check if updated
                        existing_record = existing.data[0]
                        if existing_record.get('last_modified') != file_info['modified']:
                            # Update existing record
                            supabase.table("marcel_gpt_incident_reports") \
                                .update({
                                    'last_modified': file_info['modified'],
                                    'file_url': file_info['url'],
                                    'file_size_bytes': file_info['size'],
                                    'processing_status': 'pending',
                                    'updated_at': datetime.now().isoformat()
                                }) \
                                .eq("id", existing_record['id']) \
                                .execute()

                            results['updated_files'] += 1
                    else:
                        # New file - insert
                        supabase.table("marcel_gpt_incident_reports").insert({
                            'tenant_id': self.tenant_id,
                            'sharepoint_id': file_info['id'],
                            'file_name': file_info['name'],
                            'file_url': file_info['url'],
                            'file_size_bytes': file_info['size'],
                            'uploaded_date': file_info['created'],
                            'last_modified': file_info['modified'],
                            'processing_status': 'pending'
                        }).execute()

                        results['new_files'] += 1

                    if callback:
                        await callback('progress', idx + 1, results['total_found'])

                except Exception as e:
                    results['failed'] += 1
                    results['errors'].append(f"Error processing {file_info['name']}: {str(e)}")

            return results

        except Exception as e:
            results['errors'].append(f"Sync failed: {str(e)}")
            return results
