"""Utility endpoints for WireGuard key generation and other utilities."""

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from ..core.containers import Container
from ..services.wireguard import WireGuardService

router = APIRouter()


class DerivePublicKeyRequest(BaseModel):
    private_key: str


@router.get("/generate-keypair")
@inject
async def generate_keypair(
    wireguard_service: WireGuardService = Depends(Provide[Container.wireguard_service])
):
    """
    Generate a WireGuard private/public key pair.
    
    Returns:
        dict: Contains 'private_key' and 'public_key'
    """
    private_key, public_key = wireguard_service.generate_keypair()
    return {
        "private_key": private_key,
        "public_key": public_key
    }


@router.get("/generate-preshared-key")
@inject
async def generate_preshared_key(
    wireguard_service: WireGuardService = Depends(Provide[Container.wireguard_service])
):
    """
    Generate a WireGuard preshared key.
    
    Returns:
        dict: Contains 'preshared_key'
    """
    psk = wireguard_service.generate_preshared_key()
    return {"preshared_key": psk}


@router.post("/derive-public-key")
@inject
async def derive_public_key(
    request: DerivePublicKeyRequest,
    wireguard_service: WireGuardService = Depends(Provide[Container.wireguard_service])
):
    """
    Derive public key from a private key.
    
    Args:
        request: Contains 'private_key'
    
    Returns:
        dict: Contains 'public_key'
    """
    try:
        public_key = wireguard_service.derive_public_key(request.private_key)
        return {"public_key": public_key}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to derive public key: {str(e)}"
        ) from e
