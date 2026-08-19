#!/bin/bash
# Тяжёлые базы корпуса чужого SQL: таблицы 11–100 млн строк, один
# дифференциальный прогон — минуты. Идут последовательно: 15 ГБ памяти.
cd "$(dirname "$0")/.."
source ../.venv/bin/activate
for spec in "event event_user-repeat event_user-ignore event_user-attendance" \
            "hm hm_user-churn hm_item-sales" \
            "amazon amazon_user-churn amazon_item-churn amazon_user-ltv amazon_item-ltv"; do
  set -- $spec; tag=$1; shift
  echo "=== $tag: $* ===" 
  python -u sqloracle.py "$@" --seeds 2 --suffix "_$tag"
done
