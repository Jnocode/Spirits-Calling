#include "SpiritsPlayerState.h"
#include "Net/UnrealNetwork.h"

ASpiritsPlayerState::ASpiritsPlayerState()
{
}

void ASpiritsPlayerState::AddSouls(int32 Amount)
{
	if (HasAuthority())
	{
		Souls = FMath::Max(0, Souls + Amount);
	}
}

bool ASpiritsPlayerState::TrySpendSouls(int32 Amount)
{
	if (!HasAuthority() || Souls < Amount)
	{
		return false;
	}
	Souls -= Amount;
	return true;
}

void ASpiritsPlayerState::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const
{
	Super::GetLifetimeReplicatedProps(OutLifetimeProps);
	DOREPLIFETIME(ASpiritsPlayerState, TeamId);
	DOREPLIFETIME(ASpiritsPlayerState, Souls);
}
