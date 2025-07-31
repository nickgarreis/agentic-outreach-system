# Client Members - Multi-User Access Control

This document describes the client members system that enables multiple users to collaborate on clients with role-based permissions.

## Overview

The client members system transforms the simple one-to-many (user → clients) relationship into a flexible many-to-many relationship with role-based access control. Multiple users can now access the same client with different permission levels.

## User Roles

### Owner
- **Full access** to all client data and operations
- Can **manage all members** (invite, remove, change roles)
- Can **delete the client**
- Can **transfer ownership** to other members
- At least one owner must exist per client

### Admin  
- **Full access** to client data (read/write)
- Can **manage members** (invite users, remove users, change user roles)
- **Cannot manage other owners** or admins
- Cannot delete the client

### User
- **Read-only access** to client data
- Can view client details, campaigns, leads, and messages
- **Cannot modify** any data
- **Cannot manage members**

## Database Schema

### client_members Table

```sql
CREATE TABLE client_members (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id uuid NOT NULL REFERENCES clients(id),
    user_id uuid NOT NULL REFERENCES auth.users(id), 
    role text NOT NULL CHECK (role IN ('owner', 'admin', 'user')),
    created_at timestamptz DEFAULT now(),
    invited_by uuid REFERENCES auth.users(id),
    invited_at timestamptz DEFAULT now(),
    accepted_at timestamptz, -- NULL for pending invitations
    UNIQUE(client_id, user_id)
);
```

### Key Features
- **Many-to-many relationship** between users and clients
- **Role-based permissions** with owner/admin/user hierarchy
- **Invitation system** with pending/accepted states
- **Audit trail** showing who invited whom and when

## API Endpoints

All endpoints are prefixed with `/api/clients/{client_id}/members`

### List Members
```http
GET /api/clients/{client_id}/members
```
- Lists all accepted members of a client
- Add `?include_pending=true` to include pending invitations
- **Authorization**: Any member of the client

### Invite Member
```http
POST /api/clients/{client_id}/members
Content-Type: application/json

{
    "user_email": "user@example.com",
    "role": "user",
    "message": "Optional invitation message"
}
```
- Invites a user by email to join the client
- **Authorization**: Owner or Admin

### Accept Invitation
```http
POST /api/clients/{client_id}/members/accept
```
- Accepts a pending invitation to join the client
- **Authorization**: The invited user only

### Update Member Role
```http
PUT /api/clients/{client_id}/members/{user_id}
Content-Type: application/json

{
    "role": "admin"
}
```
- Updates a member's role
- **Authorization**: Owner or Admin
- **Restrictions**: Cannot demote sole owner

### Remove Member
```http
DELETE /api/clients/{client_id}/members/{user_id}
```
- Removes a member from the client
- Members can remove themselves
- **Authorization**: Owner/Admin (to remove others) or self
- **Restrictions**: Cannot remove sole owner

## Row Level Security (RLS)

All database tables enforce role-based access through RLS policies:

### Clients Table
- **SELECT**: Members can view clients they belong to
- **INSERT**: Any authenticated user can create clients (becomes owner)
- **UPDATE**: Owners and admins can update client details
- **DELETE**: Only owners can delete clients

### Campaigns, Leads, Messages Tables
- Inherit access from parent client through `client_members` table
- **SELECT**: Any member can view
- **INSERT**: Any member can create
- **UPDATE/DELETE**: Owners and admins only

## Usage Examples

### Creating a Client Team

1. **User A creates a client** (becomes owner automatically)
2. **User A invites User B as admin**:
   ```http
   POST /api/clients/123/members
   {"user_email": "userb@example.com", "role": "admin"}
   ```
3. **User B accepts invitation**:
   ```http
   POST /api/clients/123/members/accept
   ```
4. **User B invites User C as user**:
   ```http
   POST /api/clients/123/members
   {"user_email": "userc@example.com", "role": "user"}
   ```

### Permission Scenarios

```javascript
// Owner permissions
const ownerAccess = {
    canRead: true,
    canWrite: true,
    canManageMembers: true,
    canDeleteClient: true
};

// Admin permissions  
const adminAccess = {
    canRead: true,
    canWrite: true,
    canManageMembers: true, // except owners
    canDeleteClient: false
};

// User permissions
const userAccess = {
    canRead: true,
    canWrite: false,
    canManageMembers: false,
    canDeleteClient: false
};
```

## Security Considerations

### Protection Mechanisms
- **Sole Owner Protection**: Cannot remove or demote the last owner
- **Role Hierarchy**: Admins cannot manage owners or other admins
- **Self-Management**: Users can always remove themselves (except sole owners)
- **RLS Enforcement**: Database-level access control prevents unauthorized data access

### Best Practices
- Always have at least one owner per client
- Use admin role for trusted collaborators who need write access
- Use user role for read-only access (reporting, viewing)
- Regularly audit member lists and roles

## Migration from Legacy System

The migration preserves all existing client relationships:

1. **Existing clients** with `user_id` are migrated to `client_members`
2. **Original users become owners** of their clients
3. **Old `user_id` column is removed** after migration completes
4. **All RLS policies updated** to use `client_members` table

## Troubleshooting

### Common Issues

**"Access denied: Not a member of this client"**
- User needs to be invited and accept invitation first
- Check if invitation is pending

**"Cannot change role of sole owner"** 
- Promote another member to owner first
- Then demote the original owner

**"Cannot remove sole owner"**
- Transfer ownership to another member first
- Then remove the original owner

### Validation Commands

```bash
# Run migration validation
python src/testing/validate_client_members_migration.py

# Run unit tests
python -m pytest src/testing/test_client_members.py
```

## Future Enhancements

Potential improvements to consider:

- **Invitation expiration** with configurable timeout
- **Bulk member management** for large teams
- **Role-based permissions customization** beyond the three standard roles
- **Activity logging** for member management actions
- **Email notifications** for invitations and role changes