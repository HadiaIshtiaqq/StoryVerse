// DTOs mirroring the FastAPI responses. Property names are PascalCase here and are mapped to the
// API's snake_case automatically by ApiClient's SnakeCaseNamingStrategy.
using System;
using System.Collections.Generic;

namespace Storyverse.Data
{
    [Serializable] public class AuthResponse { public string Token; public PlayerInfo Player; }
    [Serializable] public class PlayerInfo { public string Id; public string Username; }

    [Serializable]
    public class Resources
    {
        public int Gold, Food, Wood, Stone, Iron;
        public int Get(string r) => r switch { "gold" => Gold, "food" => Food, "wood" => Wood, "stone" => Stone, "iron" => Iron, _ => 0 };
    }

    [Serializable]
    public class KingdomData
    {
        public string Id, WorldId, Name, Title, Specialization, RulerName, EmblemKey, Color;
        public float MapX, MapY;
        public bool IsNpc, HasRuler;
        public int Prestige, Population, Soldiers, ArmyEstimate, Betrayals, PrestigePenalty;
        public Resources Resources;                       // null when viewing someone else's kingdom
        public Dictionary<string, int> YieldPerTurn;
        public Dictionary<string, int> PrestigeBreakdown;
    }

    [Serializable]
    public class BuildingData
    {
        public string Id, KingdomId, BuildingType, Label, State;
        public int Level, CreatedTurn;
        public float X, Y, Z, RotationY;                  // X/Z are map coordinates in [0,1]
    }

    [Serializable]
    public class CatalogEntry
    {
        public string BuildingType, Label, Function, Category, Lore;
        public Dictionary<string, int> Cost, Production, Maintenance;
        public int MaxLevel;
        public Dictionary<int, Dictionary<string, int>> UpgradeCosts;
    }

    [Serializable] public class Reason { public string Label; public int Value; }

    /// <summary>An NPC ruler's itemised verdict. Show every reason; this is what makes NPCs feel fair.</summary>
    [Serializable]
    public class Decision
    {
        public bool Accept; public int Positive, Negative, Threshold;
        public string DecidedBy, Summary; public List<Reason> Reasons;
    }

    [Serializable]
    public class TradeData
    {
        public string Id, SenderId, ReceiverId, OfferedResource, RequestedResource, Status;
        public int OfferedAmount, RequestedAmount, CreatedTurn; public Decision Decision;
    }

    [Serializable]
    public class LoanData
    {
        public string Id, Code, LenderId, BorrowerId, ProposerId, Status;
        public int Principal, DurationTurns, TotalRepayment, Installment, AmountRepaid, Remaining, MissedPayments;
        public float InterestRate; public int? AcceptedTurn, DueTurn; public Decision Decision;
    }

    [Serializable]
    public class AllianceData
    {
        public string Id, KingdomA, KingdomB, ProposerId, Status, EndedBy;
        public int DurationTurns, CreatedTurn; public int? ExpiresTurn; public bool MutualDefense; public Decision Decision;
    }

    [Serializable]
    public class WarData { public string Id, AttackerId, DefenderId, Status, PeaceProposedBy; public bool Betrayal; public int StartedTurn; }

    [Serializable]
    public class BattleData
    {
        public string Id, WarId, AttackerId, DefenderId, Outcome, PlaceName;
        public int AttackerCommitted, DefenderSoldiers, AttackerLosses, DefenderLosses, PlunderGold, Turn;
        public float AttackerPower, DefenderPower;
    }

    [Serializable] public class ActionGate { public bool Allowed; public string Reason; public string Warning; }
    [Serializable] public class StandingReason { public int Delta; public string Reason; public int Turn; }

    [Serializable]
    public class RelationData
    {
        public string KingdomId, Name, Title, RulerName, EmblemKey, Color, Band, WarId;
        public bool IsNpc; public int Standing, Trend, CreditLimitFromThem;
        public List<StandingReason> RecentReasons; public AllianceData Alliance, PendingAlliance;
        public Dictionary<string, ActionGate> Actions;   // trade, gift, loan, alliance, declare_war, peace, passage
        public PassageData PassageGranted, PassageReceived;   // my roads open to them / theirs open to me
    }

    [Serializable] public class PassageData { public string Id, GrantorId, GranteeId, Status; public int CreatedTurn; }

    [Serializable] public class GiftTier { public int Gold, Iron, StandingGain, NewStanding; public string NewBand; }
    [Serializable] public class GiftPreview { public string TargetId, Band; public int CurrentStanding, RemainingGiftGainThisTurn; public List<GiftTier> Tiers; }
    [Serializable] public class GiftResult { public int Gold, Iron, StandingGain, Standing; }

    [Serializable]
    public class MessageData { public string Id, SenderKingdomId, RecipientKingdomId, Subject, Body, Tone, CreatedAt; public bool Read; public int Turn; }

    [Serializable]
    public class StoryEventData
    {
        public string Id, EventType, Title, Description, CreatedAt;
        public List<string> Actors, Consequences; public int Importance, Turn;
    }

    [Serializable] public class NotificationData { public string Id, Kind, Text, RefType, RefId; public bool Read; public int Turn; }

    [Serializable]
    public class LeaderboardRow
    {
        public int Rank, Prestige, Penalty; public string KingdomId, Name, RulerName; public bool IsNpc;
        public Dictionary<string, int> Breakdown; public List<string> Crowns;
    }

    [Serializable] public class WorldInfo { public string Id, Name, Preset, Status; public int Turn, BeginnerProtectionTurns, TurnLimit; }
    /// <summary>POST /worlds/{id}/turn. In a shared world Advanced is false until every human ruler is ready.</summary>
    [Serializable] public class TurnResult { public string WorldId; public int Turn; public bool Advanced; public List<string> WaitingFor; }

    [Serializable]
    public class Inbox { public List<TradeData> Trades; public List<LoanData> Loans; public List<AllianceData> Alliances; public List<WarData> Peace; }

    /// <summary>GET /kingdoms/{id}/dashboard: one call feeds the wrist ledger, desk and inbox.</summary>
    [Serializable]
    public class Dashboard
    {
        public WorldInfo World; public KingdomData Kingdom; public List<BuildingData> Buildings;
        public List<RelationData> Relations; public Inbox Inbox; public List<TradeData> OutgoingTrades;
        public List<LoanData> Loans; public List<NotificationData> Notifications; public List<LeaderboardRow> Leaderboard;
        public List<DecreeData> Decrees; public List<AdviserData> Council;
        public MarketView Market; public List<UltimatumData> Ultimatums;   // Royal Market; open tribute demands
    }

    /// <summary>The Royal Market: gold per unit to buy from / sell to the crown, and this turn's remaining capacity.</summary>
    [Serializable] public class MarketPrice { public int Buy, Sell; }
    [Serializable] public class MarketView { public bool Open; public Dictionary<string, MarketPrice> Prices; public int UnitsPerTurn, UnitsLeft; }
    [Serializable] public class MarketResult { public string Resource, Side; public int Amount, Gold, Price, UnitsLeft; }

    /// <summary>An open demand for tribute. Safe = your defence at the deadline is too strong for them to attack.</summary>
    [Serializable]
    public class UltimatumData
    {
        public string FromId, From, Ruler;
        public int Amount, Paid, Owed, DeadlineTurn, TurnsLeft, TheirArmy, YourDefense, DefenseNeeded;
        public bool Safe;
    }

    /// <summary>A Royal Decree (objective). Complete ones can be claimed for their reward.</summary>
    [Serializable] public class DecreeData { public string Key, Title, Goal, Kind, Target; public int Progress, Need; public bool Complete; public Dictionary<string, int> Reward; }
    /// <summary>A member of the Royal Council and their counsel (urgency 0..2).</summary>
    [Serializable] public class AdviserData { public string Name, Role, Domain, Portrait, Advice; public int Urgency; }

    [Serializable] public class MapKingdom { public string Id, Name, Color, EmblemKey; public float MapX, MapY; public bool IsNpc; }
    [Serializable] public class TreatyLink { public string Id, A, B, Attacker, Defender; public bool Betrayal; public int? ExpiresTurn; }
    [Serializable] public class Treaties { public List<TreatyLink> Alliances, Wars; public List<PassageLink> Passages; }
    [Serializable] public class PassageLink { public string Id, Grantor, Grantee; }
    [Serializable] public class WorldMap { public int Turn; public List<MapKingdom> Kingdoms; public List<BuildingData> Buildings; public Treaties Treaties; }

    [Serializable] public class SinceReport { public int FromTurn, CurrentTurn; public List<NotificationData> Notifications; public List<StoryEventData> Chronicle; }
}
