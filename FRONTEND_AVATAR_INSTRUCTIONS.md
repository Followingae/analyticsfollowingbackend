# FRONTEND AVATAR SYSTEM IMPLEMENTATION

## BACKEND STATUS: ✅ FULLY OPERATIONAL
Server running at: `http://localhost:8000`

## FRONTEND IMPLEMENTATION GUIDE

### 1. AVATAR PRIORITY SYSTEM OVERVIEW

**Avatar Display Priority:**
1. **Custom uploaded avatar** (Supabase Storage) - **Highest priority**
2. **Instagram profile picture** (via CORSPROXY.IO) - **Fallback**  
3. **Generated initials** - **Final fallback**

### 2. API ENDPOINTS READY FOR USE

#### A. Upload Avatar
```typescript
// Upload new avatar
const uploadAvatar = async (file: File): Promise<{
  success: boolean;
  avatar_url: string;
  message: string;
}> => {
  const formData = new FormData();
  formData.append('file', file);
  
  const response = await fetch('/api/v1/user/avatar/upload', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${jwtToken}`,
    },
    body: formData,
  });
  
  return response.json();
};
```

#### B. Get Current Avatar
```typescript
// Get user's current avatar
const getCurrentAvatar = async (): Promise<{
  avatar_url: string;
  has_custom_avatar: boolean;
  uploaded_at?: string;
  file_size?: number;
  processed_size?: string;
}> => {
  const response = await fetch('/api/v1/user/avatar', {
    headers: {
      'Authorization': `Bearer ${jwtToken}`,
    },
  });
  
  return response.json();
};
```

#### C. Delete Avatar
```typescript
// Delete custom avatar (reverts to Instagram pic)
const deleteAvatar = async (): Promise<{
  success: boolean;
  message: string;
  reverted_to: string;
}> => {
  const response = await fetch('/api/v1/user/avatar', {
    method: 'DELETE',
    headers: {
      'Authorization': `Bearer ${jwtToken}`,
    },
  });
  
  return response.json();
};
```

#### D. Complete Profile with Avatar Priority
```typescript
// Get complete user profile with avatar priority
const getCompleteProfile = async (): Promise<{
  user: UserProfile;
  avatar: {
    current_url: string;
    has_custom_avatar: boolean;
  };
  instagram: {
    profile_pic_url?: string;
    profile_pic_url_hd?: string;
  };
  meta: {
    avatar_priority: 'custom' | 'instagram' | 'initials';
  };
}> => {
  const response = await fetch('/api/v1/user/profile/complete', {
    headers: {
      'Authorization': `Bearer ${jwtToken}`,
    },
  });
  
  return response.json();
};
```

### 3. FRONTEND IMPLEMENTATION STEPS

#### Step 1: Avatar Display Component
```tsx
// components/Avatar.tsx
interface AvatarProps {
  size?: 'sm' | 'md' | 'lg' | 'xl';
  className?: string;
  fallbackToInitials?: boolean;
}

const Avatar: React.FC<AvatarProps> = ({
  size = 'md',
  className = '',
  fallbackToInitials = true
}) => {
  const [avatarUrl, setAvatarUrl] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  
  useEffect(() => {
    loadAvatar();
  }, []);
  
  const loadAvatar = async () => {
    try {
      setLoading(true);
      const profile = await getCompleteProfile();
      setAvatarUrl(profile.avatar.current_url);
    } catch (err) {
      console.error('Failed to load avatar:', err);
      setError(true);
    } finally {
      setLoading(false);
    }
  };
  
  const handleError = () => {
    if (fallbackToInitials) {
      // Show initials as final fallback
      setError(true);
    }
  };
  
  const sizeClasses = {
    sm: 'w-8 h-8',
    md: 'w-12 h-12', 
    lg: 'w-16 h-16',
    xl: 'w-24 h-24'
  };
  
  if (loading) {
    return (
      <div className={`${sizeClasses[size]} bg-gray-200 rounded-full animate-pulse ${className}`} />
    );
  }
  
  if (error || !avatarUrl) {
    // Show initials fallback
    return (
      <div className={`${sizeClasses[size]} bg-blue-500 text-white rounded-full flex items-center justify-center font-semibold ${className}`}>
        {/* Get initials from user data */}
        JD
      </div>
    );
  }
  
  return (
    <img
      src={avatarUrl}
      alt="User avatar"
      className={`${sizeClasses[size]} rounded-full object-cover ${className}`}
      onError={handleError}
    />
  );
};
```

#### Step 2: Avatar Upload Component
```tsx
// components/AvatarUpload.tsx
const AvatarUpload: React.FC = () => {
  const [uploading, setUploading] = useState(false);
  const [preview, setPreview] = useState<string>('');
  const fileInputRef = useRef<HTMLInputElement>(null);
  
  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    
    // Validate file
    if (!file.type.startsWith('image/')) {
      toast.error('Please select an image file');
      return;
    }
    
    if (file.size > 5 * 1024 * 1024) { // 5MB limit
      toast.error('Image must be less than 5MB');
      return;
    }
    
    // Show preview
    const reader = new FileReader();
    reader.onload = (e) => setPreview(e.target?.result as string);
    reader.readAsDataURL(file);
    
    // Upload immediately
    handleUpload(file);
  };
  
  const handleUpload = async (file: File) => {
    try {
      setUploading(true);
      const result = await uploadAvatar(file);
      
      if (result.success) {
        toast.success('Avatar updated successfully!');
        // Refresh avatar across the app
        window.dispatchEvent(new CustomEvent('avatarUpdated'));
      } else {
        toast.error('Failed to upload avatar');
      }
    } catch (error) {
      console.error('Upload error:', error);
      toast.error('Upload failed');
    } finally {
      setUploading(false);
    }
  };
  
  const handleDelete = async () => {
    try {
      const result = await deleteAvatar();
      if (result.success) {
        toast.success('Avatar removed - reverted to Instagram picture');
        setPreview('');
        window.dispatchEvent(new CustomEvent('avatarUpdated'));
      }
    } catch (error) {
      toast.error('Failed to delete avatar');
    }
  };
  
  return (
    <div className="space-y-4">
      <div className="flex items-center space-x-4">
        <Avatar size="xl" />
        
        <div className="space-y-2">
          <Button
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
            className="flex items-center space-x-2"
          >
            {uploading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Uploading...</span>
              </>
            ) : (
              <>
                <Upload className="w-4 h-4" />
                <span>Upload New Avatar</span>
              </>
            )}
          </Button>
          
          <Button
            variant="outline"
            size="sm"
            onClick={handleDelete}
            className="text-red-600 hover:text-red-700"
          >
            Remove Custom Avatar
          </Button>
        </div>
      </div>
      
      <input
        ref={fileInputRef}
        type="file"
        accept="image/*"
        onChange={handleFileSelect}
        className="hidden"
      />
      
      <p className="text-sm text-gray-500">
        Recommended: Square image, at least 400x400px. Max 5MB.
        <br />
        Supported formats: JPG, PNG, WebP
      </p>
    </div>
  );
};
```

#### Step 3: Integration with Existing User Settings

```tsx
// In your existing settings page/component
const UserSettings: React.FC = () => {
  return (
    <div className="space-y-6">
      {/* Avatar Section */}
      <Card>
        <CardHeader>
          <CardTitle>Profile Picture</CardTitle>
          <CardDescription>
            Upload a custom avatar or use your Instagram profile picture
          </CardDescription>
        </CardHeader>
        <CardContent>
          <AvatarUpload />
        </CardContent>
      </Card>
      
      {/* Rest of your settings form */}
      {/* ... */}
    </div>
  );
};
```

### 4. AVATAR STATE MANAGEMENT

#### Option A: Using TanStack Query (Recommended)
```tsx
// hooks/useAvatar.ts
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';

export const useAvatar = () => {
  const queryClient = useQueryClient();
  
  // Get current avatar
  const { data: avatar, isLoading } = useQuery({
    queryKey: ['user-avatar'],
    queryFn: getCurrentAvatar,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
  
  // Upload mutation
  const uploadMutation = useMutation({
    mutationFn: uploadAvatar,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['user-avatar'] });
      queryClient.invalidateQueries({ queryKey: ['user-profile'] });
    },
  });
  
  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: deleteAvatar,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['user-avatar'] });
      queryClient.invalidateQueries({ queryKey: ['user-profile'] });
    },
  });
  
  return {
    avatar,
    isLoading,
    upload: uploadMutation.mutate,
    delete: deleteMutation.mutate,
    isUploading: uploadMutation.isPending,
    isDeleting: deleteMutation.isPending,
  };
};
```

#### Option B: Using Context/State Management
```tsx
// context/AvatarContext.tsx
const AvatarContext = createContext<{
  avatarUrl: string;
  hasCustomAvatar: boolean;
  refreshAvatar: () => Promise<void>;
}>({
  avatarUrl: '',
  hasCustomAvatar: false,
  refreshAvatar: async () => {},
});

export const AvatarProvider: React.FC<{ children: React.ReactNode }> = ({
  children
}) => {
  const [avatarUrl, setAvatarUrl] = useState('');
  const [hasCustomAvatar, setHasCustomAvatar] = useState(false);
  
  const refreshAvatar = useCallback(async () => {
    try {
      const profile = await getCompleteProfile();
      setAvatarUrl(profile.avatar.current_url);
      setHasCustomAvatar(profile.avatar.has_custom_avatar);
    } catch (error) {
      console.error('Failed to refresh avatar:', error);
    }
  }, []);
  
  useEffect(() => {
    refreshAvatar();
    
    // Listen for avatar updates
    const handleAvatarUpdate = () => refreshAvatar();
    window.addEventListener('avatarUpdated', handleAvatarUpdate);
    
    return () => {
      window.removeEventListener('avatarUpdated', handleAvatarUpdate);
    };
  }, [refreshAvatar]);
  
  return (
    <AvatarContext.Provider value={{
      avatarUrl,
      hasCustomAvatar,
      refreshAvatar,
    }}>
      {children}
    </AvatarContext.Provider>
  );
};
```

### 5. TESTING CHECKLIST

- [ ] **Avatar Upload**: Test with various image formats (JPG, PNG, WebP)
- [ ] **File Size Validation**: Test 5MB+ files to ensure proper error handling
- [ ] **Avatar Display**: Verify priority system (custom → Instagram → initials)
- [ ] **Delete Functionality**: Ensure custom avatar deletion reverts to Instagram pic
- [ ] **Error Handling**: Test network failures and invalid files
- [ ] **Loading States**: Verify upload progress and loading indicators
- [ ] **Mobile Responsiveness**: Test on different screen sizes

### 6. SECURITY NOTES

✅ **File Upload Security**: Backend validates file types and sizes
✅ **RLS Security**: Users can only access their own avatars
✅ **Image Processing**: All images auto-processed to 400x400px JPEG
✅ **Storage Integration**: Direct Supabase Storage with signed URLs

### 7. PERFORMANCE OPTIMIZATIONS

- **Caching**: Avatar URLs cached for 5 minutes
- **Optimized Images**: All avatars processed to 400x400px
- **Progressive Loading**: Show skeleton/placeholder while loading
- **Error Recovery**: Graceful fallback to Instagram pics or initials

---

## BACKEND ENDPOINTS SUMMARY

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/user/avatar/upload` | POST | Upload new avatar |
| `/api/v1/user/avatar` | GET | Get current avatar info |
| `/api/v1/user/avatar` | DELETE | Delete custom avatar |
| `/api/v1/user/profile/complete` | GET | Complete profile with avatar priority |

## IMPLEMENTATION COMPLETE ✅

The avatar system backend is fully operational and ready for frontend integration. Follow the steps above to implement a complete avatar management system with proper fallbacks and security.